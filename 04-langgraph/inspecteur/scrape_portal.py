# =====================================================================
# INSPECTEUR — Scraper autonome du portail marchespublics.gov.ma
#
# Inspiré de la logique VALIDÉE EN LIVE dans soukna/workflow/tools/portal.py
# (postback PRADO recherche rapide + recherche avancée paginée), mais
# AUTONOME : aucun import du projet soukna. INSPECTEUR scrape par lui-même.
#
# Deux modes :
#   full        : 1er run — couverture maximale « en cours » (cible 6000+)
#                 via recherche avancée paginée en parallèle par mot-clé.
#   incremental : runs quotidiens — recherche rapide 30 termes (~minutes),
#                 ne garde que les AO vus depuis la dernière collecte (24 h).
#
# Robustesse production :
#   - checkpoint par mot-clé écrit après CHAQUE page (aucune perte si arrêt)
#   - fusion + import DB idempotent (ON CONFLICT DO NOTHING)
#   - filtre « en cours » (échéance >= aujourd'hui)
#   - déduplication par source_ref
#   - résilience : un terme en échec n'empêche pas les autres
#
# Usage :
#   py scrape_portal.py --mode full      --target 6000 --workers 6
#   py scrape_portal.py --mode incremental --hours 24
#   py scrape_portal.py --mode import-only
# =====================================================================
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from html import unescape
from pathlib import Path
from typing import Any
from unicodedata import normalize
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests

# -------------------------------------------------------------------
# Chemins / config
# -------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass
ROOT = HERE.parent.parent  # Sou9na-Projet
STATE_DIR = HERE / "_scrape_state"
CHECKPOINT_DIR = STATE_DIR / "checkpoints"
FULL_OUTPUT = ROOT / "tenders_scraped_full.json"
INC_OUTPUT = ROOT / "tenders_scraped.json"
STATE_FILE = STATE_DIR / "scrape_state.json"

sys.path.insert(0, str(ROOT / "02-backend"))
_env = ROOT / "02-backend" / ".env"
for _line in _env.read_text(encoding="utf-8-sig").splitlines():
    _line = _line.strip()
    if _line and not _line.startswith("#") and "=" in _line:
        _k, _v = _line.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip())

BASE = "https://www.marchespublics.gov.ma"
SEARCH_PAGE = f"{BASE}/index.php"
SEARCH_PARAMS = {"page": "entreprise.EntrepriseAdvancedSearch", "AllCons": None,
                 "EnCours": None, "searchAnnCons": None}
QUICK_SEARCH_FIELD = "ctl0$menuGaucheEntreprise$quickSearch"
QUICK_SEARCH_BUTTON = "ctl0$menuGaucheEntreprise$imageOk"
UA = {"User-Agent": "Mozilla/5.0 (compatible; SouknaBot/1.0; +https://soukna.ma)",
      "Accept-Language": "fr-FR,fr;q=0.9"}
TIMEOUT = 45

# 30 termes de couverture (identique au référentiel soukna — validé live).
SEARCH_TERMS: dict[str, str] = {
    "Informatique": "informatique", "Numérique": "numérique",
    "Logiciel": "logiciel", "Cybersécurité": "cybersécurité",
    "Travaux & BTP": "travaux", "Construction": "construction",
    "Réhabilitation": "réhabilitation", "Fournitures": "fourniture",
    "Mobilier": "mobilier", "Équipements": "équipement",
    "Maintenance": "maintenance", "Énergie": "électricité",
    "Eau & assainissement": "assainissement", "Télécoms": "télécom",
    "Nettoyage": "nettoyage", "Gardiennage": "gardiennage",
    "Transport": "transport", "Impression": "imprimerie",
    "Formation": "formation", "Études & conseil": "étude",
    "Audit": "audit", "Architecture": "architecture",
    "Traduction": "traduction", "Photographie": "photographie",
    "Catering & traiteur": "traiteur", "Agroalimentaire": "alimentaire",
    "Santé & médical": "médical", "Environnement": "déchets",
    "Communication": "communication", "Bons de commande": "bons de commande",
}

MONTHS_FR = {"janv": 1, "fevr": 2, "févr": 2, "mars": 3, "avr": 4, "mai": 5,
             "juin": 6, "juil": 7, "aout": 8, "août": 8, "sept": 9, "oct": 10,
             "nov": 11, "dec": 12, "déc": 12}

REGION_MAP = {
    "rabat": "rabat-sale-kenitra", "casablanca": "casa-settat",
    "tanger": "tanger-tetouan-al-hoceima", "fes": "fes-meknes",
    "marrakech": "marrakech-safi", "agadir": "souss-massa",
    "oujda": "oriental", "meknes": "fes-meknes",
    "tetouan": "tanger-tetouan-al-hoceima", "kenitra": "rabat-sale-kenitra",
    "sale": "rabat-sale-kenitra", "el jadida": "casa-settat",
    "mohammedia": "casa-settat", "beni mellal": "beni-mellal-khenifra",
    "errachidia": "draa-tafilalet", "ouarzazate": "draa-tafilalet",
    "laayoune": "laayoune-sakia-el-hamra", "dakhla": "dakhla-oued-ed-dahab",
    "guelmim": "guelmim-oued-noun", "settat": "casa-settat",
    "safi": "marrakech-safi", "essaouira": "marrakech-safi",
    "nador": "oriental", "taza": "fes-meknes",
    "khouribga": "beni-mellal-khenifra", "khemisset": "rabat-sale-kenitra",
    "berrechid": "casa-settat", "bouskoura": "casa-settat",
    "ain harrouda": "casa-settat",
}


def wait_for_portal(max_wait_hours: float = 12.0, check_every_s: int = 300) -> bool:
    """Attend que le portail soit accessible (ouvre 07:30-00:00 heure MA).

    Le portail renvoie une page 503 « Site temporairement indisponible »
    hors de cette fenêtre. On sonde /index.php jusqu'à ce que le formulaire
    PRADO (PRADO_PAGESTATE) soit de nouveau présent.
    """
    deadline = time.time() + max_wait_hours * 3600
    first = True
    while time.time() < deadline:
        try:
            r = requests.get(SEARCH_PAGE, params=SEARCH_PARAMS,
                             headers=UA, timeout=TIMEOUT)
            if r.status_code == 200 and "PRADO_PAGESTATE" in r.text:
                print(f"Portail accessible — début scrape {datetime.now().isoformat()}",
                      flush=True)
                return True
            state = f"HTTP {r.status_code}"
            if "temporairement indisponible" in r.text.lower() or "indisponible" in r.text.lower():
                state += " (maintenance nocturne 00:00-07:30)"
        except Exception as exc:
            state = str(exc)[:80]
        if first:
            print(f"Portail indisponible ({state}) — attente ouverture 07:30…", flush=True)
            first = False
        else:
            print(f"  [{datetime.now().strftime('%H:%M:%S')}] toujours indisponible "
                  f"({state}) — nouvel essai dans {check_every_s}s", flush=True)
        time.sleep(check_every_s)
    print("Délai d'attente dépassé — abandon", flush=True)
    return False


# -------------------------------------------------------------------
# Parsing HTML (copié/adapté de la logique validée soukna)
# -------------------------------------------------------------------
def _parse_form(html: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    form_m = re.search(r'<form[^>]*id="ctl0_ctl2"[^>]*>(.*?)</form>', html, re.S)
    scope = form_m.group(1) if form_m else html
    for m in re.finditer(r"<input\b[^>]*>", scope):
        tag = m.group(0)
        name_m = re.search(r'name="([^"]+)"', tag)
        if not name_m:
            continue
        type_m = re.search(r'type="([^"]+)"', tag)
        itype = (type_m.group(1).lower() if type_m else "text")
        if itype not in {"hidden", "text"}:
            continue
        value_m = re.search(r'value="([^"]*)"', tag)
        fields[name_m.group(1)] = value_m.group(1) if value_m else ""
    return fields


def _strip_tags(block: str) -> list[str]:
    text = re.sub(r"<script.*?</script>", " ", block, flags=re.S)
    text = re.sub(r"<[^>]+>", "\n", text)
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return [line for line in lines if line]


def _after_label(lines: list[str], label: str, stops: tuple[str, ...]) -> str:
    residues = {":", "...", "…", "•"}
    for i, line in enumerate(lines):
        m = re.match(label + r"\s*:?\s*(.*)$", line, re.I)
        if m:
            same_line = m.group(1).strip()
            j = i + 1
            while j < len(lines) and lines[j] in residues:
                j += 1
            out: list[str] = []
            if same_line and same_line not in residues:
                out.append(same_line)
            for nxt in lines[j:]:
                if not nxt or nxt in residues or any(nxt.startswith(s) for s in stops):
                    break
                out.append(nxt)
            return " ".join(out).strip()
    return ""


def _parse_deadline(text: str) -> str | None:
    return _parse_date_time(text)[0]


def _parse_date_time(text: str) -> tuple[str | None, str | None]:
    from tender_times import clock_after_date

    numeric = re.search(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b", text)
    if numeric:
        try:
            day, month, year = map(int, numeric.groups())
            return date(year, month, day).isoformat(), clock_after_date(text[numeric.end():])
        except ValueError:
            return None, None
    m = re.search(r"(\d{1,2})\s+([A-Za-zÀ-ÿ]{3,9})\.?\s+(\d{4})", text)
    if not m:
        return None, None
    month_key = normalize("NFKD", m.group(2).lower()).encode("ascii", "ignore").decode()[:4]
    month = MONTHS_FR.get(month_key) or MONTHS_FR.get(month_key[:3])
    if not month:
        return None, None
    try:
        return date(int(m.group(3)), month, int(m.group(1))).isoformat(), clock_after_date(text[m.end():])
    except ValueError:
        return None, None


def _parse_rows(html: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for n in range(60):
        marker = f'id="ctl0_CONTENU_PAGE_resultSearch_tableauResultSearch_ctl{n}_'
        start = html.find(marker)
        if start == -1:
            break
        next_marker = f'id="ctl0_CONTENU_PAGE_resultSearch_tableauResultSearch_ctl{n + 1}_'
        end = html.find(next_marker, start)
        if end != -1:
            tag_start = html.rfind("<", start, end)
            if tag_start != -1:
                end = tag_start
        block = html[start:end if end != -1 else start + 25000]
        lines = _strip_tags(block)

        ref_m = re.search(
            rf'id="ctl0_CONTENU_PAGE_resultSearch_tableauResultSearch_ctl{n}_referencem"[^>]*>([^<]+)<',
            block,
        )
        link_m = re.search(r'href="([^"]*EntrepriseDetailsConsultation[^"]*)"', block)
        title = _after_label(lines, r"Objet\b", ("Détail", "Estimation", "Acheteur", "Date"))
        buyer = _after_label(lines, r"Acheteur public\b", ("Estimation", "Date", "Lieu"))
        place = _after_label(lines, r"Lieu d.exécution\b", ("AOO", "AOJR", "Référence", "Détail"))
        amount = _after_label(lines, r"Estimation TTC[^:]*", ("Acheteur", "Date", "Lieu"))
        deadline_text = _after_label(
            lines, r"Date(?: et heure)? limite de remise des plis\b",
            ("Lieu", "Acheteur", "Référence", "Détail"),
        )
        deadline, heure_remise = _parse_date_time(deadline_text)
        publication, heure_publication = _parse_date_time(_after_label(
            lines, r"Date(?: de)? (?:mise en ligne|publication)\b",
            ("Date", "Lieu", "Acheteur", "Référence"),
        ))
        offer_type = "appel_offres" if any(re.fullmatch(r"AO[A-Z]*", line) for line in lines) else "consultation"

        ref = (ref_m.group(1).strip() if ref_m else "")
        if not ref and link_m:
            idm = re.search(r"refConsultation=(\d+)", link_m.group(1))
            ref = f"ref{idm.group(1)}" if idm else f"blk{n}"
        source_ref = f"portal:{ref}"

        city = place.title() if place else ""
        href = link_m.group(1) if link_m else ""
        url = urljoin(SEARCH_PAGE, unescape(href)) if href else ""
        items.append({
            "source_ref": source_ref, "title": title[:250] or f"Consultation {ref}",
            "buyer": buyer[:180], "city": city, "region": city, "sector": "",
            "domain_code": "", "deadline": deadline, "amount": amount[:80],
            "date_publication": publication, "heure_publication": heure_publication,
            "heure_remise": heure_remise,
            "url": url, "offer_type": offer_type, "raw": {"ref": ref},
        })
    return items


def _is_en_cours(item: dict[str, Any]) -> bool:
    """Garde les annonces qui publient une échéance de remise."""
    dl = item.get("deadline")
    if not dl:
        return False
    try:
        return date.fromisoformat(dl) >= date.today()
    except ValueError:
        return False


# -------------------------------------------------------------------
# Scraping — recherche rapide (incrémental)
# -------------------------------------------------------------------
def quick_search(term: str) -> list[dict[str, Any]]:
    with requests.Session() as session:
        session.headers.update(UA)
        r0 = session.get(SEARCH_PAGE, params=SEARCH_PARAMS, timeout=(8, TIMEOUT))
        r0.raise_for_status()
        fields = _parse_form(r0.text)
        if "PRADO_PAGESTATE" not in fields:
            raise RuntimeError("PRADO_PAGESTATE introuvable")
        fields[QUICK_SEARCH_FIELD] = term
        fields[QUICK_SEARCH_BUTTON] = "OK"
        fields["PRADO_POSTBACK_TARGET"] = QUICK_SEARCH_BUTTON
        r1 = session.post(SEARCH_PAGE, params=SEARCH_PARAMS, data=fields, timeout=(8, TIMEOUT))
        r1.raise_for_status()
        return _parse_rows(r1.text)


def scrape_incremental(per_term: int = 60, workers: int = 6) -> list[dict[str, Any]]:
    """30 recherches rapides en parallèle — ~2-3 min."""
    collected: dict[str, dict[str, Any]] = {}
    failed = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(quick_search, term): (sector, term)
                   for sector, term in SEARCH_TERMS.items()}
        for fut in as_completed(futures):
            sector, term = futures[fut]
            try:
                items = fut.result()
            except Exception as exc:
                failed += 1
                print(f"  ! terme {term}: {exc}")
                continue
            new = 0
            for item in items[:per_term]:
                key = _tender_identity(item)[2]
                if key not in collected:
                    item["sector"] = sector
                    item["source"] = "portal"
                    collected[key] = item
                    new += 1
            print(f"  + {sector:24s} → {len(items):3d} lignes ({new} nouveaux)")
    ranked = sorted(collected.values(),
                    key=lambda x: (x.get("deadline") is None, x.get("deadline") or ""))
    ranked = [x for x in ranked if _is_en_cours(x)]
    if failed:
        raise RuntimeError(f"Collecte incompl?te : {failed} recherches en ?chec")
    print(f"  TOTAL en cours : {len(ranked)}")
    return ranked


# -------------------------------------------------------------------
# Scraping — recherche avancée paginée (full)
# -------------------------------------------------------------------
def advanced_search(keyword: str, max_pages: int, checkpoint_path: Path,
                    log: Any = None) -> dict[str, Any]:
    """Walk paginé pour 1 mot-clé. Checkpoint après chaque page."""
    def say(msg: str):
        line = f"[{keyword}] {msg}"
        print(line, flush=True)
        if log:
            log.write(line + "\n"); log.flush()

    s = requests.Session()
    s.headers.update(UA)
    try:
        r0 = s.get(SEARCH_PAGE, params=SEARCH_PARAMS, timeout=TIMEOUT)
        fields = _parse_form(r0.text)
        if keyword:
            fields["ctl0$CONTENU_PAGE$AdvancedSearch$keywordSearch"] = keyword
        submit = "ctl0$CONTENU_PAGE$AdvancedSearch$lancerRecherche"
        fields[submit] = "Lancer la recherche"
        fields["PRADO_POSTBACK_TARGET"] = submit
    except Exception as exc:
        say(f"init failed: {exc}")
        return {"keyword": keyword, "items": [], "pages": 0, "error": str(exc)}

    collected: dict[str, dict[str, Any]] = {}
    repeats = 0
    pages = 0
    while pages < max_pages:
        try:
            r = s.post(SEARCH_PAGE, params=SEARCH_PARAMS, data=fields, timeout=TIMEOUT)
            html = r.text
        except Exception as exc:
            say(f"page {pages+1} request failed: {exc}")
            break
        pages += 1
        items = _parse_rows(html)
        if not items:
            say(f"page {pages}: vide — arrêt")
            break
        new = [i for i in items if str(i.get("source_ref")) not in collected]
        for it in items:
            it["sector"] = keyword
            it["source"] = "portal"
            collected[str(it["source_ref"])] = it
        say(f"page {pages}: {len(items)} lignes, {len(new)} nouveaux, total={len(collected)}")

        # checkpoint atomique
        tmp = checkpoint_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(list(collected.values()), ensure_ascii=False),
                       encoding="utf-8")
        tmp.replace(checkpoint_path)

        if new:
            repeats = 0
        else:
            repeats += 1
            if repeats >= 3:
                say("pages répétées — arrêt honnête")
                break
            time.sleep(2.0)
            continue

        m = re.search(
            r'id="ctl0_CONTENU_PAGE_resultSearch_PagerBottom_(ctl\d+)"'
            r'[^>]*>\s*<img[^>]*fleche-suivant', html)
        if not m:
            say("dernière page atteinte")
            break
        fields = _parse_form(html)
        fields["PRADO_POSTBACK_TARGET"] = (
            f"ctl0$CONTENU_PAGE$resultSearch$PagerBottom${m.group(1)}")
        if keyword:
            fields["ctl0$CONTENU_PAGE$AdvancedSearch$keywordSearch"] = keyword
        fields["PRADO_POSTBACK_PARAMETER"] = "next"
        time.sleep(1.0)

    say(f"FIN: {len(collected)} uniques sur {pages} pages")
    return {"keyword": keyword, "items": list(collected.values()),
            "pages": pages, "error": None}


def scrape_full(target: int, workers: int, max_pages: int) -> list[dict[str, Any]]:
    """Couverture maximale : tous les mots-clés en parallèle, checkpoints."""
    CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = STATE_DIR / "full_scrape.log"
    merged: dict[str, dict[str, Any]] = {}
    # reprise : recharge les checkpoints existants
    for cp in CHECKPOINT_DIR.glob("*.json"):
        try:
            for item in json.loads(cp.read_text(encoding="utf-8-sig")):
                merged[_tender_identity(item)[2]] = item
        except Exception:
            pass
    print(f"Reprise : {len(merged)} tenders déjà en checkpoint")

    with log_path.open("a", encoding="utf-8") as log:
        log.write(f"\n=== RUN {datetime.now().isoformat()} target={target} ===\n")
        # priorité aux termes à forte couverture, puis les autres
        terms = list(SEARCH_TERMS.values())
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {}
            for term in terms:
                if len(merged) >= target:
                    break
                cp = CHECKPOINT_DIR / f"cp_{re.sub(r'[^a-z0-9]+', '_', term.lower())}.json"
                futures[pool.submit(advanced_search, term, max_pages, cp, log)] = term
            for fut in as_completed(futures):
                term = futures[fut]
                try:
                    res = fut.result()
                except Exception as exc:
                    print(f"  ! {term}: {exc}")
                    continue
                for item in res["items"]:
                    merged[_tender_identity(item)[2]] = item
                print(f"  ✓ {term:24s} → {len(res['items'])} uniques "
                      f"(pages={res['pages']}) — cumul={len(merged)}")

    ranked = sorted(merged.values(),
                    key=lambda x: (x.get("deadline") is None, x.get("deadline") or ""))
    ranked = [x for x in ranked if _is_en_cours(x)][:target]
    FULL_OUTPUT.write_text(json.dumps(ranked, ensure_ascii=False, indent=2),
                           encoding="utf-8")
    print(f"ÉCRIT {FULL_OUTPUT.name}: {len(ranked)} tenders en cours")
    return ranked


# -------------------------------------------------------------------
# Import DB (idempotent)
# -------------------------------------------------------------------
def map_region(city: str | None) -> str:
    low = (city or "").lower().strip()
    for key, region in REGION_MAP.items():
        if key in low:
            return region
    return (city or "").strip() or "-"


def _montant_vers_int(valeur: str) -> int:
    """Convertit '2 880 000,00' en 2880000 (MAD entiers)."""
    valeur = (valeur or "").replace("\u00a0", " ").strip()
    valeur = valeur.replace(" ", "")
    if "," in valeur:
        valeur = valeur.replace(".", "").replace(",", ".")
    else:
        valeur = valeur.replace(".", "")
    try:
        return int(round(float(valeur)))
    except (ValueError, TypeError):
        return 0


def parse_amount(text: str) -> tuple[int, int]:
    montant, caution = 0, 0
    estimate = re.split(r"\bcaution\b", text or "", maxsplit=1, flags=re.I)[0]
    m = re.search(r"([\d\s]+,\d{2})", estimate)
    if m:
        montant = _montant_vers_int(m.group(1))
    cm = re.search(r"caution[^:]*:\s*([\d\s]+,\d{2})", text or "", re.I)
    if cm:
        caution = _montant_vers_int(cm.group(1))
    # Un montant inconnu reste NULL : on n'invente jamais de valeur.
    if montant <= 0:
        return 0, caution
    return montant, caution


_TRACKING_KEYS = {
    "fbclid", "gclid", "mc_cid", "mc_eid", "_ga", "igshid", "msclkid",
}


def canonical_url(raw: str | None) -> str:
    """Même contract que public.soukna_canonical_url (migration 011).

    On normalise schéma, host, www, port par défaut, slashes, trailing slash,
    paramètres de tracking et ordre des paramètres. Le fragment est supprimé.
    """
    value = (raw or "").strip().lower()
    if not value:
        return ""
    if "://" not in value:
        value = "https://" + value
    try:
        parts = urlsplit(value)
        host = (parts.hostname or "").lower()
        port = parts.port
    except ValueError:
        return value.split("#")[0]
    if host.startswith("www."):
        host = host[4:]
    if (parts.scheme == "http" and port == 80) or (parts.scheme == "https" and port == 443):
        port = None
    netloc = host + (f":{port}" if port else "")
    path = re.sub(r"/{2,}", "/", parts.path)
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    if not path:
        path = "/"
    kept = []
    for key, val in parse_qsl(parts.query, keep_blank_values=True):
        low = key.lower()
        if low.startswith("utm_") or low in _TRACKING_KEYS:
            continue
        kept.append((key, val))
    kept.sort()
    query = urlencode(kept)
    return urlunsplit((parts.scheme.lower(), netloc, path, query, ""))


def _tender_identity(item: dict[str, Any]) -> tuple[str, str, str, tuple[str, str]]:
    """Clé stable : URL canonique d'abord, référence en secours."""
    ref = str(item.get("source_ref", "")).replace("portal:", "")
    url = str(item.get("url") or "").strip()
    url_key = canonical_url(url)
    official = portal_identity(url)
    key = ("p", official) if official else (("u", url_key) if url_key else ("r", ref))
    return ref, url, url_key, key


def portal_identity(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url)
    if parts.hostname not in {"www.marchespublics.gov.ma", "marchespublics.gov.ma"}:
        return None
    query = dict(parse_qsl(parts.query.lower()))
    consultation, organisation = query.get("refconsultation"), query.get("orgacronyme")
    if consultation and organisation:
        return f"consultation:{organisation}:{consultation}"
    notice = re.fullmatch(r"/bdc/entreprise/consultation/show/(\d+)/?", parts.path)
    return f"bdc:{notice[1]}" if notice else None


def import_to_db(items: list[dict[str, Any]], collect_date: str | None = None,
                 batch_size: int = 500) -> int:
    """Import idempotent et groupé : aucun doublon, un commit par lot."""
    import psycopg
    from psycopg import sql

    collect_date = collect_date or date.today().isoformat()
    # PgBouncer en mode transaction : les prepared statements ne survivent
    # pas au changement de connexion serveur (cf. db_cps.connect).
    conn = psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None)

    # 1) Déduplication en mémoire (une URL = un appel d'offres, même si la
    #    référence du portail change d'une page à l'autre).
    vus: set[tuple[str, str]] = set()
    uniques: list[tuple[str, str, str, dict]] = []
    for item in items:
        ref, url, url_key, key = _tender_identity(item)
        if not ref or key in vus:
            continue
        vus.add(key)
        uniques.append((ref, url, url_key, item))

    # 2) Pré-filtrage DB par lots : on ne tente même pas d'insérer un avis
    #    déjà connu (évite des milliers d'INSERT et de round-trips inutiles).
    connus_refs: set[str] = set()
    connus_urls: set[str] = set()
    connus_keys: set[str] = set()
    connus_portail: set[str] = set()
    quarantaines: dict[str, str] = {}
    with conn.cursor() as cur:
        for i in range(0, len(uniques), batch_size):
            lot = uniques[i:i + batch_size]
            refs = [r for r, _, _, _ in lot]
            urls = [u for _, u, _, _ in lot if u]
            keys = [k for _, _, k, _ in lot if k]
            consultations = [identity.rsplit(":", 1)[1] for _, url, _, _ in lot
                             if (identity := portal_identity(url)) and identity.startswith("consultation:")]
            cur.execute(
                "SELECT reference, source_url, url_key, "
                "(statut='clos' AND extraction @> '{\"quarantaine_secours\":true}'::jsonb) FROM tenders "
                "WHERE reference = ANY(%s) OR url_key = ANY(%s) OR source_url = ANY(%s) "
                "OR substring(source_url from '(?i)[?&]refConsultation=([0-9]+)') = ANY(%s)",
                (refs, keys, urls, consultations),
            )
            for row in cur.fetchall():
                connus_refs.add(row[0])
                if row[2]:
                    connus_keys.add(row[2])
                if row[1]:
                    connus_urls.add(canonical_url(row[1]))
                    if identity := portal_identity(row[1]):
                        connus_portail.add(identity)
                        if row[3]:
                            quarantaines[identity] = row[0]

    frais = []
    réactivations = []
    horaires = []
    for ref, url, url_key, item in uniques:
        if item.get("heure_publication") or item.get("heure_remise"):
            horaires.append((item.get("date_publication"), item.get("heure_publication"),
                             item.get("deadline"), item.get("heure_remise"), url_key, url))
        identity = portal_identity(url)
        if (identity in quarantaines and item.get("offer_type")
                and (item.get("deadline") or "") >= collect_date):
            réactivations.append((item["offer_type"], item["deadline"], item.get("heure_remise"), collect_date,
                                 item.get("buyer"), item.get("title"), quarantaines[identity]))
            continue
        if (identity in connus_portail or url_key in connus_keys
                or canonical_url(url) in connus_urls):
            continue
        if ref in connus_refs:
            if not identity:
                continue
            ref = f"{ref} [{identity}]"
            if ref in connus_refs:
                continue
        connus_refs.add(ref)
        frais.append((ref, url, url_key, item))

    # 3) INSERT groupés, ON CONFLICT filet de sécurité, 1 commit par lot.
    colonnes = ("reference", "organisme", "objet", "secteur", "region",
                "montant_mad", "caution_mad", "lots", "qualifications_exigees",
                "delai_jours", "date_remise", "date_publication",
                "date_collecte", "statut", "source", "source_url", "url_key", "offer_type")
    debut = sql.SQL("INSERT INTO tenders ({}) VALUES ").format(
        sql.SQL(", ").join(sql.Identifier(c) for c in colonnes))
    fin = sql.SQL(
        " ON CONFLICT (reference) DO UPDATE SET "
        "montant_mad = CASE WHEN EXCLUDED.montant_mad IS NOT NULL "
                       "THEN EXCLUDED.montant_mad ELSE tenders.montant_mad END, "
        "caution_mad = CASE WHEN EXCLUDED.caution_mad > 0 "
                       "THEN EXCLUDED.caution_mad ELSE tenders.caution_mad END "
        "WHERE tenders.url_key = EXCLUDED.url_key"
    )
    inserted = 0
    errors = 0
    with conn.cursor() as cur:
        if réactivations:
            cur.executemany(
                """
                UPDATE tenders
                SET offer_type=%s, date_remise=%s, heure_remise=%s, date_collecte=%s,
                    organisme=coalesce(nullif(%s,''),organisme),
                    objet=coalesce(nullif(%s,''),objet), statut='ouvert', source='portail',
                    extraction=extraction - 'quarantaine_secours',
                    enriched_at=NULL, enrich_next_at=NULL, enrich_attempts=0, enrich_error=NULL
                WHERE reference=%s AND statut='clos'
                  AND extraction @> '{"quarantaine_secours":true}'::jsonb
                """, réactivations,
            )
            inserted += cur.rowcount
            conn.commit()
        for i in range(0, len(frais), batch_size):
            lot = frais[i:i + batch_size]
            valeurs: list = []
            for ref, url, url_key, item in lot:
                montant, caution = parse_amount(item.get("amount", ""))
                montant_value = montant if montant > 0 else None
                deadline = item.get("deadline")
                try:
                    if deadline:
                        datetime.fromisoformat(deadline)
                except ValueError:
                    deadline = None
                valeurs.extend((
                    ref,
                    (item.get("buyer") or "")[:200],
                    (item.get("title") or "")[:500],
                    (item.get("sector") or "services").lower()[:50] or "services",
                    map_region(item.get("city", "")),
                    montant_value, caution if caution > 0 else None, [], [], None,
                    deadline, item.get("date_publication"), collect_date,
                    "ouvert", "portail", url, url_key or None, item.get("offer_type"),
                ))
            marqueurs = sql.SQL(", ").join(
                sql.SQL("({})").format(
                    sql.SQL(", ").join(sql.Placeholder() for _ in colonnes)
                ) for _ in lot
            )
            try:
                cur.execute(debut + marqueurs + fin, valeurs)
                conn.commit()
                inserted += cur.rowcount
            except Exception as exc:
                conn.rollback()
                errors += 1
                if errors <= 5:
                    print(f"  ! DB lot {i // batch_size}: {str(exc)[:120]}")
    with conn.cursor() as cur:
        if horaires:
            cur.executemany("""
                UPDATE tenders t SET
                  heure_publication=CASE WHEN p.open_time IS NOT NULL AND
                    (t.date_publication IS NULL OR t.date_publication=p.open_date)
                    THEN p.open_time ELSE t.heure_publication END,
                  date_publication=coalesce(t.date_publication,p.open_date),
                  heure_remise=CASE WHEN p.close_time IS NOT NULL AND
                    (t.date_remise IS NULL OR t.date_remise=p.close_date)
                    THEN p.close_time ELSE t.heure_remise END,
                  date_remise=coalesce(t.date_remise,p.close_date)
                FROM (VALUES (%s::date,%s::time,%s::date,%s::time,%s::text,%s::text))
                     AS p(open_date,open_time,close_date,close_time,url_key,source_url)
                WHERE (nullif(p.url_key,'') IS NOT NULL AND t.url_key=p.url_key)
                   OR (nullif(p.source_url,'') IS NOT NULL AND t.source_url=p.source_url)
            """, horaires)
            conn.commit()
        cur.execute("SELECT count(*) FROM tenders")
        total = cur.fetchone()[0]
    conn.close()
    doublons = len(items) - len(frais)
    print(f"DB: +{inserted} insérés, {doublons} doublons filtrés, "
          f"{errors} erreurs, total={total}")
    if errors:
        raise RuntimeError(f"Import incomplet : {errors} erreurs PostgreSQL")
    return inserted


# -------------------------------------------------------------------
# État (pour incrémental)
# -------------------------------------------------------------------
def load_state() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8-sig"))
        except Exception:
            pass
    return {"last_scrape": None}


def save_state(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                          encoding="utf-8")


# -------------------------------------------------------------------
# CLI
# -------------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser(description="INSPECTEUR — scrape AO en cours")
    ap.add_argument("--mode", choices=["full", "incremental", "import-only"],
                    default="incremental")
    ap.add_argument("--target", type=int, default=6000)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--max-pages", type=int, default=40)
    ap.add_argument("--per-term", type=int, default=60)
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--no-import", action="store_true")
    ap.add_argument("--collect-date", default=None)
    ap.add_argument("--wait-for-portal", action="store_true",
                    help="attend l'ouverture du portail (07:30) avant de scraper")
    ap.add_argument("--max-wait-hours", type=float, default=12.0)
    args = ap.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if args.mode == "import-only":
        items = json.loads(FULL_OUTPUT.read_text(encoding="utf-8-sig"))
        print(f"Import de {len(items)} tenders (checkpoint full)")
        import_to_db(items, args.collect_date)
        return

    if args.wait_for_portal:
        if not wait_for_portal(args.max_wait_hours):
            sys.exit(2)

    if args.mode == "full":
        items = scrape_full(args.target, args.workers, args.max_pages)
    else:
        print(f"Mode incrémental ({args.hours} h) — 30 recherches rapides")
        items = scrape_incremental(args.per_term, args.workers)
        INC_OUTPUT.write_text(json.dumps(items, ensure_ascii=False, indent=2),
                              encoding="utf-8")
        print(f"ÉCRIT {INC_OUTPUT.name}: {len(items)} tenders")

    if not args.no_import:
        import_to_db(items, args.collect_date)

    state = load_state()
    state["last_scrape"] = datetime.now().isoformat()
    state["last_mode"] = args.mode
    state["last_count"] = len(items)
    save_state(state)
    print(f"État sauvegardé: {STATE_FILE}")


if __name__ == "__main__":
    main()
