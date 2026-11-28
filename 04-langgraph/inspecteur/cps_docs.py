# =====================================================================
# Cycle documents PAR OFFRE — portail national en source principale,
# aomaroc en REPLI uniquement si le portail ne livre pas le dossier.
#
# Pour chaque offre ouverte sans document ingéré :
#   1) page de détail : vraie date limite -> mise à jour (offre supprimée
#      si la deadline est déjà passée) ;
#   2) lien EntrepriseDemandeTelechargementDce -> formulaire -> ZIP DCE ;
#   3) PDFs du ZIP (CPS d'abord, dédoublonnés sha256, récursifs ZIP
#      imbriqués) -> ingestion TOTALE (même texte insuffisant) :
#      Storage optionnel + texte + sections ;
#   4) repli aomaroc si le portail échoue.
#
# Idempotent : les offres avec un document 'extracted'/'ready' sont
# sautées ; pièces dédoublonnées par sha256 (UNIQUE en base) ; les
# échecs ('echec'/'missing_cps') sont retrés au prochain cycle.
# =====================================================================
from __future__ import annotations

import hashlib
import re
import time
from datetime import date, datetime, timezone
from typing import Any

import requests

from . import config, cps_aomaroc, cps_dce, cps_extract, db


def record_failure(reference: str, source_url: str, statut: str,
                   raison: str) -> None:
    """Trace un échec/absence dans tender_documents (retrier plus tard)."""
    fake_sha = hashlib.sha256(
        f"{reference}|{statut}|{raison}".encode()).hexdigest()
    try:
        db.insert_document(
            reference=reference, doc_type=None, filename=None, mime=None,
            storage_path=None,
            sha256=fake_sha, source_url=source_url or None,
            statut=statut, echec_raison=raison, sections=0, char_count=0)
    except Exception as exc:
        print(f"[docs] WARN trace échec impossible {reference}: {exc}",
              flush=True)


def process_tender(tender: dict[str, Any], session: requests.Session,
                   uploader, today: date, fallback: bool = True) -> dict[str, Any]:
    ref = str(tender.get("reference") or "")
    keys = cps_dce.parse_portal_keys(tender.get("source_url") or "")
    if not keys:
        return {"reference": ref, "status": "skipped", "reason": "no_portal_keys"}
    refc, org = keys
    dce_url = (f"{config.PORTAL_BASE}/index.php?page=entreprise."
               f"EntrepriseDemandeTelechargementDce&refConsultation={refc}"
               f"&orgAcronyme={org}")

    existing = db.document_for(ref)
    if existing and existing.get("statut") in ("extracted", "ready"):
        return {"reference": ref, "status": "skipped", "reason": "deja_ingere"}

    # 1) page de détail : deadline réelle (+ suppression si passée)
    try:
        rd = session.get(cps_dce.detail_url(refc, org),
                         timeout=config.REQUEST_TIMEOUT_S)
        rd.raise_for_status()
    except requests.RequestException as exc:
        return {"reference": ref, "status": "portal_error",
                "reason": f"detail: {str(exc)[:120]}"}
    from .offers_status import parse_deadline_value
    dl = parse_deadline_value(rd.text)
    if dl is not None and dl >= today:
        db.set_tender_deadline(ref, dl)
    elif dl is None or dl < today:
        if config.DELETE_FINISHED_OFFERS:
            db.delete_offer(ref)
            return {"reference": ref, "status": "deleted",
                    "reason": f"deadline passee ({dl})"}

    # 2) lien de téléchargement DCE sur la page de détail
    link_m = cps_dce._DCE_LINK_RE.search(rd.text)
    if not link_m:
        record_failure(ref, cps_dce.detail_url(refc, org), "missing_cps",
                       "no_dce_link_on_portal_detail")
        return {"reference": ref, "status": "missing_cps",
                "reason": "no_dce_link_on_portal_detail"}
    href = link_m.group(1).replace("&amp;", "&")
    dce_page = href if href.startswith("http") else (
        config.PORTAL_BASE + "/" + href.lstrip("/"))

    # 3) formulaire + ZIP (portail)
    zip_bytes: bytes | None = None
    portal_reason = ""
    try:
        zip_bytes = cps_dce.fetch_dce_zip(session, dce_page)
    except (cps_dce.DceError, requests.RequestException) as exc:
        portal_reason = f"portail: {str(exc)[:150]}"
    source_url = dce_page

    # 4) REPLI aomaroc
    used_fallback = False
    if not zip_bytes:
        if not config.AO_ENABLED or not fallback:
            record_failure(ref, dce_page, "echec", portal_reason[:200])
            return {"reference": ref, "status": "echec",
                    "reason": portal_reason or "no_zip_from_portal"}
        try:
            zip_bytes = cps_aomaroc.fetch_relay_zip(session, refc, org)
            used_fallback = True
            source_url = cps_dce.cps_relay_url(refc, org)
        except (cps_aomaroc.AomarocError, requests.RequestException) as exc:
            record_failure(ref, dce_page, "echec",
                           f"{portal_reason} | aomaroc: {str(exc)[:150]}")
            return {"reference": ref, "status": "echec",
                    "reason": f"{portal_reason} | aomaroc: {str(exc)[:120]}"}

    # 5) PDFs du dossier -> ingestion totale
    pdfs = cps_dce.pdfs_from_zip(zip_bytes)[:config.MAX_DOCS_PER_TENDER]
    if not pdfs:
        record_failure(ref, source_url, "missing_cps", "no_pdf_in_dce_zip")
        return {"reference": ref, "status": "missing_cps",
                "reason": "no_pdf_in_dce_zip"}

    ref_dir = cps_dce.sanitize_path_part(ref.replace("/", "_"))
    ingested: list[dict[str, Any]] = []
    for name, data in pdfs:
        sha = hashlib.sha256(data).hexdigest()
        if db.sha_exists(sha):
            ingested.append({"filename": name, "status": "deja_vu"})
            continue
        doc_type = cps_dce.classify_doc_type(name)
        fname = cps_dce.sanitize_path_part(name)
        info = cps_extract.extract_text(data)
        sections = cps_extract.split_into_sections(info["text"])
        # consigne : ingestion TOTALE — un PDF scanné sans couche texte
        # reste stocké ; la faible qualité est tracée sans bloquer
        has_text = info["char_count"] >= cps_extract.MIN_TEXT_CHARS
        if info["pages"] and info["pages"] > 0:
            statut = "extracted"
            echec_raison = (None if has_text else
                            f"texte insuffisant ({info['char_count']} chars)")
        else:
            statut = "echec"
            echec_raison = "pdf illisible (aucune page)"
        storage_path = None
        if uploader is not None:
            try:
                storage_path = uploader(f"{ref_dir}/{fname}", data)
            except Exception as exc:
                statut = "echec"
                echec_raison = f"storage_upload_failed: {str(exc)[:150]}"
        try:
            doc_id = db.insert_document(
                reference=ref, doc_type=doc_type, filename=fname,
                mime="application/pdf", storage_path=storage_path, sha256=sha,
                size_bytes=len(data), pages=info["pages"],
                extraction=info["extraction"], extracted_text=info["text"],
                source_url=source_url, statut=statut,
                echec_raison=echec_raison, sections=len(sections),
                char_count=info["char_count"])
            if sections and statut == "extracted":
                db.replace_sections(doc_id, sections)
            ingested.append({"doc_type": doc_type, "filename": fname,
                             "status": statut})
        except Exception as exc:
            ingested.append({"filename": fname, "status": "db_error",
                             "reason": str(exc)[:120]})

    ok = [d for d in ingested if d.get("status") == "extracted"]
    if not ok:
        record_failure(ref, source_url, "echec", "no_pdf_ingested")
        return {"reference": ref, "status": "echec",
                "reason": "no_pdf_ingested", "documents": ingested}
    return {"reference": ref, "status": "ok", "fallback": used_fallback,
            "deadline": str(dl), "documents": ingested}


def collect_docs(minutes: float | None = None, limit: int = 60,
                 store_originals: bool | None = None,
                 fallback: bool = True) -> dict[str, Any]:
    """Cycle documents sur toutes les offres ouvertes sans document."""
    minutes = minutes if minutes is not None else config.DOCS_MINUTES
    today = date.today()
    tenders = db.offers_without_documents(limit)
    print(f"[docs] {len(tenders)} offre(s) sans document", flush=True)
    uploader = None
    if store_originals is None:
        store_originals = config.STORE_ORIGINALS
    if store_originals:
        from . import storage
        uploader = storage.make_uploader()
        if uploader is None:
            print("[docs] WARN storage indisponible — texte seul en DB",
                  flush=True)

    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT,
                            "Referer": config.PORTAL_BASE + "/"})
    stats: dict[str, int] = {"ok": 0, "deleted": 0, "missing_cps": 0,
                             "echec": 0, "skipped": 0, "portal_error": 0,
                             "fallback": 0}
    t0 = time.monotonic()
    for tender in tenders:
        if time.monotonic() - t0 > minutes * 60.0:
            print("[docs] budget atteint, arrêt propre", flush=True)
            break
        try:
            res = process_tender(tender, session, uploader, today,
                                 fallback=fallback)
        except Exception as exc:
            res = {"reference": tender.get("reference", "?"),
                   "status": "echec", "reason": f"unexpected: {str(exc)[:150]}"}
        stats[res["status"]] = stats.get(res["status"], 0) + 1
        if res.get("fallback"):
            stats["fallback"] += 1
        docs = res.get("documents")
        print(f"[docs] {res['reference']}: {res['status']} "
              f"{res.get('reason') or (docs if docs else '')}", flush=True)
        time.sleep(config.PORTAL_DELAY_S)
    return stats


# -----------------------------------------------------------------------
# Extraction des champs riches depuis le texte CPS/RC
# -----------------------------------------------------------------------

_MONTANT_RE = re.compile(
    r"(?:estimation(?:\s+ttc)?|montant\s+(?:global\s+)?(?:des\s+travaux|des"
    r"\s+prestations|des\s+fournitures|des\s+services|pr[ée]visionnel|estim[ée]"
    r"|g[ée]n[ée]ral)|budget\s+estimatif|co[ûu]t\s+estimatif|prix\s+global|"
    r"estim[ée]e?s?\s+[àa])[^.;\n]{0,140}?"
    r"\(?\s*(\d[\d\u00a0\u202f\u2009 .]{2,24}(?:,\d{1,2})?)\s*\)?"
    r"\s*(?:DH|DHS|MAD|dirhams?)", re.I)
_MONTANT_FALLBACK_RE = re.compile(
    r"(?:montant\s+du\s+march[ée]|montant\s+global|montant\s+total|estim[ée]"
    r"\s+[àa])[^.;\n]{0,100}?"
    r"\(?\s*(\d[\d\u00a0\u202f\u2009 .]{2,24}(?:,\d{1,2})?)\s*\)?"
    r"\s*(?:DH|DHS|MAD|dirhams?)", re.I)
_CAUTION_RE = re.compile(
    r"(?:cautionnement\s+provisoire|caution\s+provisoire|"
    r"garantie\s+temporaire|cautionnement\s+bancaire)"
    r"[^.;\n]{0,170}?"
    r"\(?\s*(\d[\d\u00a0\u202f\u2009 .]{2,24}(?:,\d{1,2})?)\s*\)?"
    r"\s*(?:DH|DHS|MAD|dirhams?)", re.I)
_DELAI_RE = re.compile(
    r"d[ée]lai\s+(?:global\s+)?(?:d[’']?ex[ée]cution|de\s+r[ée]alisation|"
    r"contractuel)[^.;\n]{0,100}?"
    r"(?:(\d{1,4})|\w+\s*\((\d{1,4})\))\s*(jours?|mois|semaines?|ans?)", re.I)
_QUALIF_RE = re.compile(
    r"qualification[^.;\n]{0,60}?\b([A-K])\s*[.\-/]\s*(\d{1,2})"
    r"(?:[^.;\n]{0,40}?classe\s*[: ]?\s*(\d{1,2}))?", re.I)
_QUALIF2_RE = re.compile(
    r"classe\s*(?:et\s+cat[ée]gorie)?\s*[:=]\s*([A-K])\s*[.\-/]\s*(\d{1,2})",
    re.I)
_AGREMENT_RE = re.compile(
    r"agr[ée]ment\s+(?:\w+\s+){0,4}?n[°o]?\s*:?\s*([A-Z0-9][^.;\n]{2,60})", re.I)
_LOT_RE = re.compile(
    r"[Ll][Oo][Tt]\s+n\s*[°o]\s*(\d{1,2})\s*[:\-–]\s*"
    r"(.*?)(?=\s*(?:\n|[Ll][Oo][Tt]\s+n\s*[°o]\s*\d|$))")
_UNIT_DAYS = {"jour": 1, "jours": 1, "semaine": 7, "semaines": 7,
              "mois": 30, "trimestre": 90, "trimestres": 90,
              "an": 365, "ans": 365}
# priorité document : CPS d'abord (clauses), puis RC, puis avis
_DOC_ORDER = {"CPS": 0, "DCE": 1, "ADDITIF": 2, "AVIS": 3}


def parse_num(txt: str | None) -> float | None:
    """7 256 110,80 / 55.000,00 / 1 500 000 -> float."""
    if not txt:
        return None
    s = re.sub(r"[^\d,.\-]", "", str(txt)).strip(".,-")
    if not s:
        return None
    if "," in s:
        intpart, _, dec = s.rpartition(",")
        intpart = intpart.replace(".", "").replace(",", "")
        s = intpart + "." + (dec or "0")
    elif s.count(".") > 1:
        parts = s.split(".")
        s = "".join(parts[:-1]) + "." + parts[-1]
    elif s.count(".") == 1:
        head, _, tail = s.partition(".")
        if len(tail) == 3 and head:
            s = head + tail  # 55.000 = milliers
    try:
        v = float(s)
        return v if 0 < v < 5e10 else None
    except ValueError:
        return None


def extract_fields(text: str) -> dict[str, Any]:
    """Champs riches déduits d'un texte CPS/RC/avis (dict partiel)."""
    out: dict[str, Any] = {}
    clean = re.sub(r"\s+", " ", text)
    m = _MONTANT_RE.search(clean) or _MONTANT_FALLBACK_RE.search(clean)
    if m:
        v = parse_num(m.group(1))
        if v:
            out["montant_mad"] = v
    c = _CAUTION_RE.search(clean)
    if c:
        v = parse_num(c.group(1))
        if v:
            out["caution_mad"] = v
    d = _DELAI_RE.search(clean)
    if d:
        n = int(d.group(1) or d.group(2))
        unit = d.group(3).lower()
        days = n * _UNIT_DAYS.get(unit, n * _UNIT_DAYS.get(unit.rstrip("s"), 0))
        if 0 < days <= 3650:
            out["delai_jours"] = days
    quals: list[str] = []
    for q in _QUALIF_RE.finditer(clean):
        item = f"{q.group(1)}.{q.group(2)}"
        if q.group(3):
            item += f" : Classe {q.group(3)}"
        if item not in quals:
            quals.append(item)
    if not quals:
        for q in _QUALIF2_RE.finditer(clean):
            item = f"{q.group(1)}.{q.group(2)}"
            if item not in quals:
                quals.append(item)
    for a in _AGREMENT_RE.finditer(clean):
        item = f"Agrément : {a.group(1).strip()}"
        if item not in quals and len(quals) < 10:
            quals.append(item)
    if quals:
        out["qualifications_exigees"] = quals[:10]
    lots: list[str] = []
    seen_no: set[int] = set()
    for lm in _LOT_RE.finditer(text):
        no = int(lm.group(1))
        if no in seen_no:
            continue
        seen_no.add(no)
        title = re.sub(r"\s+", " ", lm.group(2)).strip()
        lots.append(f"Lot {no} - {title[:100]}")
        if len(lots) >= 20:
            break
    if lots:
        out["lots"] = lots
    return out


def extract_all_fields(minutes: float | None = None,
                       limit: int = 2000) -> dict[str, int]:
    """Remplit les champs vides des offres ayant des documents extraits."""
    minutes = minutes if minutes is not None else config.FIELDS_MINUTES
    targets = db.offers_missing_fields(limit)
    print(f"[fields] {len(targets)} offre(s) avec docs et champs manquants",
          flush=True)
    stats = {"processed": 0, "updated": 0, "montant": 0, "caution": 0,
             "lots": 0, "qualifications": 0, "delai": 0}
    t0 = time.monotonic()
    base_key = {"montant_mad": "montant", "caution_mad": "caution",
                "lots": "lots", "qualifications_exigees": "qualifications",
                "delai_jours": "delai"}
    for t in targets:
        if time.monotonic() - t0 > minutes * 60.0:
            print("[fields] budget atteint, arrêt propre", flush=True)
            break
        ref = t["reference"]
        texts = db.documents_texts(ref)
        texts.sort(key=lambda r: _DOC_ORDER.get(r.get("doc_type") or "DCE", 9))
        found: dict[str, Any] = {}
        for row in texts:
            for key, value in extract_fields(row["extracted_text"]).items():
                found.setdefault(key, value)
        updates = {}
        for key, value in found.items():
            cur = t.get(key)
            empty = (cur is None or cur == [] or cur == {}
                     or (key == "delai_jours" and cur in (None, 0)))
            if empty:
                updates[key] = value
        if not updates:
            stats["processed"] += 1
            continue
        db.update_tender_fields(ref, updates)
        stats["updated"] += 1
        for key in updates:
            stats[base_key[key]] += 1
        print(f"[fields] {ref}: +{', '.join(updates.keys())}", flush=True)
    return stats
