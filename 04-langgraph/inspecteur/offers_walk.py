# =====================================================================
# Marche du listing portail (recherche avancée paginée) avec :
#   • reprise entre exécutions : PRADO_PAGESTATE lié au cookie de session
#     PHP — cookies + champs persistés après CHAQUE page
#     (portal_walk_state.json) ;
#   • collecte brute en JSONL (audit_map.jsonl) : chaque ligne = une offre
#     telle que listée (reference, url, titre, acheteur, montant, lieu,
#     deadline) — sert au ré-audit des offres absentes de la base ;
#   • upsert idempotent des offres dans 'tenders' : les offres à deadline
#     passée ne sont PAS insérées (le portail garde en ligne les annonces
#     terminées des années) ;
#   • garde-fou portail fermé : hors fenêtre 07:00-00:30 (Maroc), une page
#     vide ne termine JAMAIS la marche.
# =====================================================================
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime, timezone
from typing import Any
from unicodedata import normalize

import requests
from requests.utils import cookiejar_from_dict, dict_from_cookiejar

from . import config, db

SEARCH_PAGE = f"{config.PORTAL_BASE}/index.php"
SEARCH_PARAMS = {"page": "entreprise.EntrepriseAdvancedSearch"}
_PAGER_NEXT = re.compile(
    r'id="ctl0_CONTENU_PAGE_resultSearch_PagerBottom_(ctl\d+)"'
    r'[^>]*>\s*<img[^>]*fleche-suivant')

MONTHS_FR = {
    "janv": 1, "fevr": 2, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
    "juil": 7, "aout": 8, "août": 8, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    "déc": 12,
}

SECTOR_KEYWORDS: list[tuple[str, list[str]]] = [
    ("Informatique", ["informatique", "numérique", "numerique", "logiciel",
                      "plateforme", "digital", "télécom", "telecom",
                      "application", "cybersécurité", "web"]),
    ("BTP", ["construction", "travaux", "réhabilitation", "bâtiment",
             "voirie", "aménagement", "route", "terrassement"]),
    ("Fournitures", ["fourniture", "acquisition", "équipement", "mobilier",
                     "matériel", "consommables"]),
    ("Services et maintenance", ["maintenance", "nettoyage", "gardiennage",
                                 "entretien", "sécurité privée", "transport"]),
    ("Conseil et études", ["étude", "etude", "conseil", "audit",
                           "assistance", "ingénierie", "formation"]),
]


def _sector_from_title(title: str) -> str:
    low = (title or "").lower()
    best, best_hits = "", 0
    for sector, words in SECTOR_KEYWORDS:
        hits = sum(1 for w in words if re.search(rf"\b{re.escape(w)}", low))
        if hits > best_hits:
            best, best_hits = sector, hits
    return best


def _parse_deadline(text: str) -> str | None:
    m = re.search(r"(\d{1,2})\s+([A-Za-zÀ-ÿ]{3,5})\.?\s+(\d{4})", text)
    if not m:
        return None
    key = normalize("NFKD", m.group(2).lower()).encode("ascii", "ignore").decode()[:4]
    month = MONTHS_FR.get(key)
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(1))).isoformat()
    except ValueError:
        return None


def _parse_form(html: str) -> dict[str, str]:
    """Champs hidden + text du formulaire principal (PRADO)."""
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


def _parse_rows(html: str) -> list[dict[str, Any]]:
    """Un bloc par index N du tableau de résultats (jusqu'à ~60 lignes)."""
    items: list[dict[str, Any]] = []
    for n in range(60):
        marker = (f'id="ctl0_CONTENU_PAGE_resultSearch_'
                  f'tableauResultSearch_ctl{n}_')
        start = html.find(marker)
        if start == -1:
            break
        next_marker = (f'id="ctl0_CONTENU_PAGE_resultSearch_'
                       f'tableauResultSearch_ctl{n + 1}_')
        end = html.find(next_marker, start)
        if end != -1:
            tag_start = html.rfind("<", start, end)
            if tag_start != -1:
                end = tag_start
        block = html[start:end if end != -1 else start + 25000]
        text = re.sub(r"<script.*?</script>", " ", block, flags=re.S)
        text = re.sub(r"<[^>]+>", "\n", text)
        lines = [re.sub(r"\s+", " ", line).strip()
                 for line in text.splitlines() if line.strip()]

        ref_m = re.search(
            rf'id="ctl0_CONTENU_PAGE_resultSearch_tableauResultSearch_ctl{n}_'
            r'referencem"[^>]*>([^<]+)<', block)
        link_m = re.search(r'href="([^"]*EntrepriseDetailsConsultation[^"]*)"', block)
        title = _after_label(lines, r"Objet\b",
                             ("Détail", "Estimation", "Acheteur", "Date"))
        buyer = _after_label(lines, r"Acheteur public\b",
                             ("Estimation", "Date", "Lieu"))
        place = _after_label(lines, r"Lieu d.exécution\b",
                             ("AOO", "AOJR", "Référence", "Détail"))
        amount = _after_label(lines, r"Estimation TTC[^:]*",
                              ("Acheteur", "Date", "Lieu"))
        deadline = _parse_deadline(block)

        ref = (ref_m.group(1).strip() if ref_m else "")
        if not ref and link_m:
            idm = re.search(r"refConsultation=(\d+)", link_m.group(1))
            ref = f"ref{idm.group(1)}" if idm else f"blk{n}"
        source_ref = f"portal:{ref}"

        city = place.title() if place else ""
        if deadline:
            try:
                dl_date = date.fromisoformat(deadline)
                if (dl_date - date.today()).days > 400:
                    deadline = None  # fin d'affichage PV : non fiable
            except ValueError:
                deadline = None
        href = link_m.group(1) if link_m else ""
        url = href if href.startswith("http") else (
            config.PORTAL_BASE + href if href else "")
        items.append({
            "source_ref": source_ref,
            "title": title[:250] or f"Consultation {ref}",
            "buyer": buyer[:180],
            "city": city,
            "deadline": deadline,
            "amount": amount[:80],
            "url": url,
        })
    return items


def parse_amount(txt: str | None) -> float | None:
    """7 256 110,80 / 55.000,00 / 1 500 000 -> float (None sinon)."""
    if not txt:
        return None
    s = re.sub(r"[^\d,.\-]", "", str(txt)).replace(",", ".")
    if s.count(".") > 1:
        parts = s.split(".")
        s = "".join(parts[:-1]) + "." + parts[-1]
    try:
        v = float(s)
        return v if 0 < v < 5e10 else None
    except ValueError:
        return None


def clean_text(txt: str | None, max_len: int | None = None) -> str:
    if not txt:
        return ""
    cleaned = re.sub(r"\s+", " ", str(txt)).strip()
    return cleaned[:max_len] if max_len else cleaned


def upsert_rows(items: list[dict[str, Any]], today: date) -> tuple[int, int]:
    """Nettoyage + upsert DB d'une page (dédupliquée par référence).

    Offres à deadline passée : NON insérées (le portail garde en ligne
    les annonces terminées). Retourne (écrites, nouvelles).
    """
    written = new = 0
    by_ref: dict[str, dict[str, Any]] = {}
    for it in items:
        ref = clean_text(it.get("source_ref"), 120)
        if not ref:
            continue
        by_ref.setdefault(ref, it)
    for ref, it in by_ref.items():
        dl_date = None
        if it.get("deadline"):
            try:
                dl_date = date.fromisoformat(str(it["deadline"]))
            except ValueError:
                dl_date = None
        if dl_date and dl_date < today:
            continue  # consigne : ne pas remplir la base avec les finies
        obj = clean_text(it.get("title")) or f"Consultation {ref}"
        city = clean_text(it.get("city"), 120) or "autre"
        buyer = clean_text(it.get("buyer"), 180) or "Inconnu"
        url = clean_text(it.get("url"), 2000)
        if buyer == "Inconnu" and not url:
            continue
        existed = db.offer_exists(ref)
        try:
            db.upsert_offer(
                reference=ref, organisme=buyer, objet=obj[:500],
                secteur=_sector_from_title(obj) or "autre", region=city,
                montant_mad=parse_amount(it.get("amount")),
                date_remise=dl_date, date_collecte=today,
                statut="ouvert", source_url=url)
            written += 1
            new += 0 if existed else 1
        except Exception as exc:
            print(f"    [ERR] upsert {ref}: {str(exc)[:120]}", flush=True)
    return written, new


def _next_fields(html: str) -> dict[str, str] | None:
    m = _PAGER_NEXT.search(html)
    if not m:
        return None
    fields = _parse_form(html)
    fields["PRADO_POSTBACK_TARGET"] = (
        f"ctl0$CONTENU_PAGE$resultSearch$PagerBottom${m.group(1)}")
    fields["PRADO_POSTBACK_PARAMETER"] = "next"
    return fields


def walk(minutes: float | None = None, max_pages: int = 400,
         audit_map: bool = False) -> dict[str, Any]:
    """Un cycle de marche : reprise sur l'état persisté, upsert/page.

    Retourne un résumé ; l'état (cookies + pagestate) est persisté après
    chaque page pour reprendre exactement là où la marche s'est arrêtée.
    """
    minutes = minutes if minutes is not None else config.WALK_MINUTES
    t0 = time.monotonic()
    budget = minutes * 60.0
    today = date.today()
    s = requests.Session()
    s.headers.update({"User-Agent": config.USER_AGENT})

    state: dict[str, Any] = {}
    try:
        state = json.loads(config.WALK_STATE_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError:
        pass

    resumed = False
    if not state.get("done") and state.get("fields") and state.get("cookies"):
        cookiejar_from_dict(state["cookies"], s.cookies)
        fields = state["fields"]
        resumed = True
        print(f"[walk] reprise à la page {state.get('pages_total', 0) + 1}...",
              flush=True)
    else:
        r0 = s.get(SEARCH_PAGE, params=SEARCH_PARAMS,
                   timeout=config.REQUEST_TIMEOUT_S)
        fields = _parse_form(r0.text)
        submit = "ctl0$CONTENU_PAGE$AdvancedSearch$lancerRecherche"
        fields[submit] = "Lancer la recherche"
        fields["PRADO_POSTBACK_TARGET"] = submit

    pages_before = state.get("pages_total", 0)
    seen: list[str] = state.get("seen_refs", [])
    seen_set = set(seen)
    chunk = {"pages": 0, "written": 0, "new": 0}
    repeats = 0
    prev_top: list[str] = state.get("prev_top", [])
    done = False
    stop = "max_pages"
    map_fh = None
    if audit_map:
        map_fh = config.AUDIT_MAP_PATH.open("a", encoding="utf-8")

    try:
        while chunk["pages"] < max_pages:
            if time.monotonic() - t0 > budget:
                stop = "budget"
                break
            r = s.post(SEARCH_PAGE, params=SEARCH_PARAMS, data=fields,
                       timeout=config.REQUEST_TIMEOUT_S)
            items = _parse_rows(r.text)
            if not items and (resumed and chunk["pages"] == 0):
                # pagestate refusé : session neuve obligatoire
                print("[walk] état portail refusé -> recherche fraîche",
                      flush=True)
                resumed = False
                prev_top, repeats = [], 0
                s = requests.Session()
                s.headers.update({"User-Agent": config.USER_AGENT})
                r0 = s.get(SEARCH_PAGE, params=SEARCH_PARAMS,
                           timeout=config.REQUEST_TIMEOUT_S)
                fields = _parse_form(r0.text)
                submit = "ctl0$CONTENU_PAGE$AdvancedSearch$lancerRecherche"
                fields[submit] = "Lancer la recherche"
                fields["PRADO_POSTBACK_TARGET"] = submit
                continue
            chunk["pages"] += 1
            top = [str(i.get("source_ref")) for i in items[:3]]
            if top and top == prev_top:
                repeats += 1
                if repeats >= 3:
                    stop = "stalled"
                    break
                time.sleep(2.0)
                continue
            repeats = 0
            prev_top = top
            if not items:
                hour = (datetime.now(timezone.utc).hour + 1) % 24
                if not (6 <= hour <= 23):
                    stop = "portal_closed"
                    break  # portail fermé : JAMAIS done
                stop = "empty"
                done = True
                break
            for it in items:
                ref = str(it.get("source_ref"))
                if ref not in seen_set:
                    seen_set.add(ref)
                    seen.append(ref)
            if map_fh is not None:
                for it in items:
                    map_fh.write(json.dumps({
                        "reference": str(it.get("source_ref") or ""),
                        "url": (it.get("url") or "")[:2000],
                        "title": it.get("title") or "",
                        "buyer": it.get("buyer") or "",
                        "amount": it.get("amount") or "",
                        "city": it.get("city") or "",
                        "deadline": it.get("deadline"),
                    }, ensure_ascii=False) + "\n")
                map_fh.flush()
            else:
                w, n = upsert_rows(items, today)
                chunk["written"] += w
                chunk["new"] += n
            nxt = _next_fields(r.text)
            pages_total = pages_before + chunk["pages"]
            print(f"[walk] page {pages_total}: {len(items)} rows, "
                  f"{len(seen_set)} uniques ({time.monotonic()-t0:.0f}s)",
                  flush=True)
            config.WALK_STATE_PATH.write_text(json.dumps({
                "done": False,
                "pages_total": pages_total,
                "prev_top": top,
                "seen_refs": seen[-5000:],
                "fields": nxt or {},
                "cookies": dict_from_cookiejar(s.cookies),
                "last": datetime.now(timezone.utc).isoformat(),
            }, ensure_ascii=False), encoding="utf-8")
            if not nxt:
                stop = "last_page"
                done = True
                break
            fields = nxt
            time.sleep(0.3)
    finally:
        if map_fh is not None:
            map_fh.close()

    return {"done": done, "stop": stop, "resumed": resumed,
            "chunk_pages": chunk["pages"], "chunk_written": chunk["written"],
            "chunk_new": chunk["new"], "uniques_total": len(seen_set),
            "pages_total": pages_before + chunk["pages"],
            "elapsed_s": round(time.monotonic() - t0, 1)}
