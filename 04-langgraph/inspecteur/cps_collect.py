# =====================================================================
# Orchestration : sélection cible -> téléchargement -> extraction -> DB.
# Idempotent, avec budget storage (free tier) et mode dry-run.
# =====================================================================
from __future__ import annotations

import hashlib
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from . import config, cps_download, cps_extract, cps_target, db, storage


def _safe_filename(url: str) -> str:
    """Nom de fichier lisible : idAvis du portail si disponible."""
    parsed = urlparse(url)
    ids = parse_qs(parsed.query).get("idAvis") or []
    if ids and ids[0].isdigit():
        return f"avis-{ids[0]}.pdf"
    name = Path(parsed.path).name
    if name.lower() in {"", "index.php", "default.aspx"}:
        name = "document.pdf"
    return "".join(c for c in name if c.isalnum() or c in ".-_ ")[:120]


def _doc_type_for(url: str) -> str:
    """Type de document déduit de l'URL de téléchargement du portail."""
    low = url.lower()
    if "cps" in low or "dce" in low:
        return "CPS"
    if "pv" in low or "resultat" in low or "attribution" in low:
        return "PV"
    return "AVIS"


def collect(*, dry_run: bool = False,
            max_docs: int | None = None,
            max_bytes: int | None = None,
            store_originals: bool | None = None,
            only_pertinent: bool = True,
            limit: int = 500,
            references: list[str] | None = None,
            request_id: str | None = None,
            session: Any = None,
            sleep: Any = None) -> dict[str, Any]:
    """Collecte les documents pertinents et les insère en base.

    Retourne un dict de statistiques (jamais d'exception pour un PDF isolé :
    chaque échec est consigné dans `failed` avec son motif).
    """
    max_docs = max_docs if max_docs is not None else config.MAX_DOCS
    max_bytes = max_bytes if max_bytes is not None else config.TOTAL_BUDGET_BYTES
    if references:  # run ciblé : la pertinence est déjà décidée par l'appelant
        only_pertinent = False
    if store_originals is None:
        store_originals = config.STORE_ORIGINALS
    sleep = sleep or time.sleep
    rid = request_id or str(uuid.uuid4())

    if not dry_run:
        db.ensure_schema()

    profiles = db.active_profiles()
    envelope = cps_target.build_envelope(
        profiles,
        sector_override=config.SECTOR_OVERRIDE or None,
        region_override=config.REGION_OVERRIDE or None,
        capacity_override=config.CAPACITY_OVERRIDE,
    )
    candidates = db.candidate_tenders(max(limit, 5000) if references else limit)
    if references:
        wanted = {str(r) for r in references}
        candidates = [t for t in candidates if str(t.get("reference")) in wanted]

    # Les autres sources (ex. one.org.ma) sont protégées par du JS : on se
    # limite au portail national, seul exploitable en HTTP simple.
    allowed_hosts = {h.strip().lower().lstrip(".") for h in config.ALLOWED_HOSTS if h.strip()}
    host_excluded = 0
    if allowed_hosts:
        kept: list[dict[str, Any]] = []
        for t in candidates:
            host = urlparse(str(t.get("source_url") or "")).netloc.lower()
            if host in allowed_hosts or any(host.endswith("." + h) for h in allowed_hosts):
                kept.append(t)
            else:
                host_excluded += 1
        candidates = kept

    selected: list[dict[str, Any]] = []
    filtered: Counter[str] = Counter()
    for tender in candidates:
        verdict = cps_target.is_pertinent(tender, envelope)
        if verdict["ok"] or not only_pertinent:
            selected.append(tender)
        else:
            filtered[verdict["reason"]] += 1

    used = 0 if dry_run else db.usage_bytes()
    budget = max(0, max_bytes - used)

    uploader = storage.make_uploader() if (store_originals and not dry_run) else None
    if store_originals and uploader is None and not dry_run:
        filtered["originals_degraded_no_creds"] += 1

    results: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    skipped: Counter[str] = Counter()
    if host_excluded:
        skipped["hors_hote_autorise"] = host_excluded
    uploaded = 0
    consecutive_failures = 0

    for tender in selected:
        if consecutive_failures >= config.MAX_CONSECUTIVE_FAILURES:
            break
        reference = str(tender.get("reference") or "")
        if not reference:
            skipped["sans_reference"] += 1
            continue
        if len(results) >= max_docs:
            skipped["max_docs_atteint"] += 1
            break
        if used >= budget:
            skipped["budget_atteint"] += 1
            break

        existing = db.document_for(reference)
        if existing and existing.get("statut") in ("extracted", "ready", "downloading"):
            skipped["deja_ingere"] += 1
            continue

        detail_url = str(tender.get("source_url") or "").strip()
        if not detail_url.startswith(("http://", "https://")):
            failed.append({"reference": reference, "reason": "source_url_absente"})
            continue

        try:
            html = cps_download.fetch_detail(detail_url, session=session)
        except cps_download.FetchError as exc:
            failed.append({"reference": reference, "reason": f"detail: {exc}"})
            consecutive_failures += 1
            continue

        pub_date = cps_download.parse_publication_date(html)
        if pub_date and not dry_run:
            db.update_tender_publication_date(reference, pub_date)

        links = cps_download.find_pdf_links(detail_url, html)[:3]
        if not links:
            failed.append({"reference": reference, "reason": "aucun_lien_pdf"})
            continue

        data = None
        last_error = ""
        filename = "document.pdf"
        doc_link = ""
        for link in links:
            try:
                data = cps_download.download_pdf(link, session=session)
                filename = _safe_filename(link)
                doc_link = link
                break
            except (cps_download.FetchError, cps_download.DocumentTooLarge,
                    cps_download.NotAPdf) as exc:
                last_error = str(exc)
        if data is None:
            failed.append({"reference": reference, "reason": f"download: {last_error}"})
            continue

        consecutive_failures = 0
        if used + len(data) > budget:
            skipped["budget_insuffisant_pdf"] += 1
            break

        sha = hashlib.sha256(data).hexdigest()
        if db.sha_exists(sha):
            skipped["hash_deja_vu"] += 1
            continue

        info = cps_extract.extract_text(data)
        if info["pages"] > config.MAX_PAGES:
            skipped["trop_de_pages"] += 1
            continue
        sections = cps_extract.split_into_sections(info["text"])
        has_text = info["char_count"] >= cps_extract.MIN_TEXT_CHARS
        statut = "extracted" if has_text else "echec"
        echec_raison = None if has_text else "texte insuffisant (< 100 chars)"

        storage_path = f"{reference}/{filename}"
        if uploader is not None:
            try:
                storage_path = uploader(storage_path, data)
                uploaded += 1
            except Exception as exc:
                statut = "echec"
                echec_raison = f"storage_upload_failed: {str(exc)[:150]}"

        if dry_run:
            results.append({
                "reference": reference, "statut": f"dry_run:{statut}",
                "bytes": len(data), "pages": info["pages"],
                "sections": len(sections), "sha256": sha,
                "storage_path": storage_path,
            })
            used += len(data)
            continue

        doc_id = db.insert_document(
            reference=reference,
            doc_type=_doc_type_for(doc_link),
            filename=filename,
            mime="application/pdf",
            storage_path=storage_path,
            sha256=sha,
            size_bytes=len(data),
            pages=info["pages"],
            extraction=info["extraction"],
            extracted_text=info["text"],
            source_url=detail_url,
            request_id=rid,
            statut=statut,
            echec_raison=echec_raison,
            sections=len(sections),
            char_count=info["char_count"],
        )
        if sections and statut == "extracted":
            db.replace_sections(doc_id, sections)

        used += len(data)
        results.append({
            "reference": reference, "document_id": doc_id, "statut": statut,
            "bytes": len(data), "pages": info["pages"], "sections": len(sections),
            "sha256": sha, "storage_path": storage_path,
        })
        sleep(config.PORTAL_DELAY_S)

    if consecutive_failures >= config.MAX_CONSECUTIVE_FAILURES:
        skipped["portail_indisponible"] += 1

    return {
        "request_id": rid,
        "dry_run": dry_run,
        "target": {
            "secteurs": sorted(envelope["sectors"]),
            "regions": sorted(envelope["regions"]),
            "capacite_max_mad": envelope["max_capacity"],
            "profils_actifs": envelope["profile_count"],
        },
        "candidats": len(candidates),
        "selectionnes": len(selected),
        "filtres": dict(filtered),
        "ignores": dict(skipped),
        "inseres": results,
        "echecs": failed,
        "octets_utilises": used,
        "octets_budget": max_bytes,
        "originaux_uplodes": uploaded,
        "stockage_originaux": bool(store_originals and uploader is not None),
    }
