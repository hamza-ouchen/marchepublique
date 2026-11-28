"""API du tableau de bord premium — données réelles, plus de fixtures."""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from psycopg.errors import UniqueViolation

from chat import repondre
from daily_jobs import enqueue, mark_init
import db_cps
from app.tools.storage import sign_download

from canaux_locaux import trace  # noqa: E402

routeur = APIRouter(prefix="/api")
_bearer = HTTPBearer(auto_error=False)


def _company_scope(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> str | None:
    from api import _check

    session = _check(creds)
    if session.get("role") == "admin":
        return None
    if session.get("role") != "entreprise" or not session.get("sub"):
        raise HTTPException(403, "Accès entreprise requis")
    rows = db_cps.query(
        "SELECT company_id FROM company_matching_profiles WHERE lower(email) = %s LIMIT 2",
        (session["sub"].strip().lower(),),
    )
    if len(rows) != 1:
        raise HTTPException(403, "Profil entreprise introuvable ou ambigu")
    return rows[0]["company_id"]


def _require_company(requested: str | None, scope: str | None) -> str:
    if scope is not None:
        if requested is not None and requested != scope:
            raise HTTPException(403, "Accès refusé à cette entreprise")
        return scope
    if not requested:
        raise HTTPException(422, "company_id requis")
    return requested


def _objet(valeur: Any, defaut: Any) -> Any:
    if isinstance(valeur, (dict, list)):
        return valeur
    if isinstance(valeur, str):
        try:
            return json.loads(valeur)
        except Exception:
            return defaut
    return defaut


def _nombre(valeur: Any) -> float | None:
    if valeur is None:
        return None
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _jour() -> str:
    return db_cps.query(
        "SELECT (now() at time zone 'Africa/Casablanca')::date::text AS jour"
    )[0]["jour"]


def _secteur_ui(valeur: str | None) -> str:
    v = (valeur or "").lower()
    if any(x in v for x in ("informatique", "numérique", "digital", "logiciel", "cyber")):
        return "it"
    if any(x in v for x in ("travaux", "construction", "bâtiment", "génie civil")):
        return "btp"
    if any(x in v for x in ("fourniture", "mobilier", "équipement", "matériel")):
        return "fournitures"
    if any(x in v for x in ("étude", "audit", "conseil", "formation")):
        return "conseil"
    return "services"


def _statut_ui(valeur: str | None) -> str:
    return {"a_etudier": "study", "envoye": "prep", "gagne": "submitted",
            "perdu": "submitted"}.get(valeur or "", "study")


def _recommandations(row: dict[str, Any], controles: dict[str, Any],
                     risques: list[str]) -> list[str]:
    """Recommandations opérationnelles, sans inventer de risque documentaire."""
    recommandations: list[str] = []
    score = int(row.get("match_total") or 0)
    verdict = (row.get("verdict") or "A_ETUDIER").upper()
    if verdict != "GO" or score < 75:
        recommandations.append(
            "Réaliser une revue complète du dossier de consultation avant dépôt : "
            "vérifier les pièces administratives, les qualifications et le délai d’exécution."
        )
    if controles.get("caution_vs_capacite") in {"risque", "inconnu", "ko"}:
        recommandations.append(
            "Valider la caution provisoire auprès de la banque et vérifier qu’elle "
            "reste compatible avec votre capacité financière."
        )
    if controles.get("qualifications") in {"risque", "inconnu", "ko"}:
        recommandations.append(
            "Rassembler les attestations et qualifications exigées, puis les joindre "
            "au dossier avant la date limite de remise."
        )
    if controles.get("delai_atteignable") in {"risque", "inconnu", "ko"}:
        recommandations.append(
            "Confirmer la faisabilité du planning avec l’équipe opérationnelle "
            "avant de s’engager."
        )
    if not recommandations:
        recommandations.append(
            "Conserver une copie horodatée du dossier déposé et suivre la publication "
            "des résultats sur le portail officiel."
        )
    if controles.get("_confiance") == "faible":
        recommandations.append(
            "Télécharger les pièces officielles (CPS, CCTP, additifs) pour renforcer "
            "la fiabilité de l’analyse avant décision finale."
        )
    return recommandations[:4]


def _conseil(row: dict[str, Any], opportunite: dict[str, Any]) -> str:
    verdict = opportunite["verdict"]
    score = opportunite["match_score"]
    if verdict == "go":
        return (
            f"Dossier prometteur (score {score}/100). Lancez la préparation administrative "
            "sans attendre, tout en contrôlant une dernière fois la caution et les pièces citées."
        )
    if verdict == "nogo":
        return (
            f"Score {score}/100 et contrôles bloquants : mieux vaut ne pas engager de moyens "
            "sur cette affaire, sauf modification officielle du dossier."
        )
    return (
        f"Score {score}/100 : le dossier mérite une étude documentaire approfondie. "
        "Sou9na n’affirme aucune pénalité ni retard : utilisez la liste « points à vérifier » "
        "comme checklist avant toute décision."
    )


def _opportunite(row: dict[str, Any]) -> dict[str, Any]:
    controles = _objet(row.get("controles"), {})
    composantes = _objet(row.get("composantes"), {})
    justifs = _objet(row.get("justifications"), []) or []
    citation = next((item for item in justifs
                     if isinstance(item, dict) and (item.get("pages") or item.get("source_url"))), None)
    raisons = [j.get("constat") for j in justifs
               if isinstance(j, dict) and j.get("constat")][:3]
    risques = _objet(row.get("risques_a_verifier"), []) or []
    reference = row["reference"]
    reference_officielle = row.get("reference_officielle") or reference
    opportunity_type = {
        "bon_de_commande": "bon_commande",
        "consultation": "consultation",
    }.get(row.get("offer_type"), "appel_offres")
    return {
        "id": reference,
        "source_ref": reference_officielle,
        "title": {"fr": row.get("objet") or reference_officielle, "ar": row.get("objet") or reference_officielle},
        "buyer": {"fr": row.get("organisme") or "", "ar": row.get("organisme") or ""},
        "city": row.get("region") or "",
        "sector": _secteur_ui(row.get("secteur")),
        "opportunity_type": opportunity_type,
        "deadline": str(row["date_remise"]) if row.get("date_remise") else "",
        "deadline_time": str(row["heure_remise"])[:5] if row.get("heure_remise") else None,
        "publication_time": str(row["heure_publication"])[:5] if row.get("heure_publication") else None,
        "publication_date": str(row["date_publication"]) if row.get("date_publication") else None,
        "amount": _nombre(row.get("montant_mad")),
        "guarantee": _nombre(row.get("caution_mad")),
        "match_score": row["match_total"],
        "verdict": {"GO": "go", "A_ETUDIER": "study", "NO_GO": "nogo"}.get(
            row.get("verdict") or "A_ETUDIER", "study"),
        "risks": [str(x) for x in risques],
        "reasons": [str(x) for x in raisons],
        "recommendations": _recommandations(row, controles, risques),
        "advice": _conseil(row, {
            "verdict": {"GO": "go", "A_ETUDIER": "study", "NO_GO": "nogo"}.get(
                row.get("verdict") or "A_ETUDIER", "study"),
            "match_score": row["match_total"],
        }),
        "breakdown": {
            "secteur": composantes.get("secteur", 0),
            "keywords": composantes.get("qualifications", 0),
            "region": composantes.get("region", 0),
            "size": composantes.get("capacite", 0),
            "history": composantes.get("historique", 0),
            "caution": composantes.get("caution", 0),
            "delai": composantes.get("delai", 0),
        },
        "confidence": controles.get("_confiance", "faible"),
        "source_preuve": controles.get("_source_preuve", "metadata_seul"),
        "citation": citation,
        "saved": bool(row.get("statut_dossier")),
        "status": _statut_ui(row.get("statut_dossier")),
        "note": row.get("note") or "",
        "url": row.get("source_url") or None,
        "is_new": False,
    }


@routeur.get("/dashboard")
def dashboard(company_id: str | None = None, date: str | None = None,
              limit: int = Query(100, ge=1, le=500),
              scope: str | None = Depends(_company_scope)) -> dict[str, Any]:
    company_id = _require_company(company_id, scope)
    date = date or _jour()
    entreprise = db_cps.query(
        "SELECT company_id, nom, secteur, region, email, canaux_optin, "
        "       init_status, init_started_at, init_error "
        "FROM company_matching_profiles WHERE company_id = %s", (company_id,)
    )
    if not entreprise:
        raise HTTPException(404, "entreprise introuvable")

    rows = db_cps.query(
        """
        SELECT s.reference, s.match_total, s.composantes, s.points_perdus,
               v.verdict, v.controles, v.justifications, v.risques_a_verifier,
               t.objet, t.organisme, t.secteur, t.region, t.montant_mad,
               t.caution_mad, t.date_remise, t.heure_remise, t.date_publication, t.heure_publication, t.source_url,
               t.reference_officielle, t.offer_type,
               f.statut_dossier, f.note
        FROM scores s
        LEFT JOIN verdicts v
          ON v.company_id = s.company_id AND v.reference = s.reference
         AND v.rendu_le >= s.calcule_le
        JOIN tenders t ON t.reference = s.reference
        LEFT JOIN favoris f
          ON f.company_id = s.company_id AND f.reference = s.reference
        WHERE s.company_id = %s AND s.calcule_le::date = %s
          AND t.statut = 'ouvert'
          AND t.date_remise >= (now() AT TIME ZONE 'Africa/Casablanca')::date
          AND (t.heure_remise IS NULL OR t.date_remise + t.heure_remise > now() AT TIME ZONE 'Africa/Casablanca')
          AND EXISTS (
              SELECT 1 FROM tender_documents d
              WHERE d.reference = t.reference
                AND (
                  (
                    d.statut IN ('extracted', 'ready')
                    AND (
                      COALESCE(d.char_count, 0) > 0
                      OR COALESCE(d.sections, 0) > 0
                      OR NULLIF(btrim(COALESCE(d.extracted_text, '')), '') IS NOT NULL
                    )
                  )
                  OR EXISTS (SELECT 1 FROM cps_sections s WHERE s.document_id = d.id)
                )
          )
        ORDER BY s.match_total DESC
        """,
        (company_id, date),
    )
    digests = db_cps.query(
        "SELECT contenu_fr, statut_envoi FROM digests "
        "WHERE company_id = %s AND jour = %s ORDER BY jour DESC LIMIT 1",
        (company_id, date),
    )
    digest = _objet(digests[0].get("contenu_fr"), {}) if digests else {}
    stats = {
        "total": len(rows),
        "go": sum(1 for r in rows if r.get("verdict") == "GO"),
        "a_etudier": sum(1 for r in rows if r.get("verdict") == "A_ETUDIER"),
        "no_go": sum(1 for r in rows if r.get("verdict") == "NO_GO"),
        "dossiers_suivis": sum(1 for r in rows if r.get("statut_dossier")),
        "init_status": entreprise[0].get("init_status") or "ready",
        "init_started_at": str(entreprise[0].get("init_started_at") or "") or None,
    }
    return {
        "date": date,
        "company": entreprise[0],
        "profile": {
            "name": entreprise[0].get("nom"),
            "sector": entreprise[0].get("secteur"),
            "region": entreprise[0].get("region"),
        },
        "init_status": stats["init_status"],
        "init_error": entreprise[0].get("init_error"),
        "stats": stats,
        "opportunities": [_opportunite(r) for r in rows[:limit]],
        "digest": digest,
        "digest_status": digests[0].get("statut_envoi") if digests else None,
    }


@routeur.get("/opportunity-document")
def opportunity_document(response: Response, reference: str = Query(min_length=1, max_length=512),
                         scope: str | None = Depends(_company_scope)) -> dict[str, str]:
    if scope is not None and not db_cps.query(
        "SELECT 1 FROM scores WHERE company_id = %s AND reference = %s LIMIT 1", (scope, reference),
    ):
        raise HTTPException(404, "Document indisponible")
    documents = db_cps.query(
        """SELECT storage_bucket, storage_path FROM tender_documents
           WHERE reference = %s AND storage_bucket IN ('tender-originaux', 'cps-originaux', 'cps_documents')
             AND NULLIF(btrim(storage_path), '') IS NOT NULL
           ORDER BY (storage_bucket = 'tender-originaux') DESC,
                    (doc_type = 'CPS') DESC NULLS LAST, id DESC LIMIT 5""", (reference,),
    )
    for document in documents:
        try:
            url = sign_download(document["storage_bucket"], document["storage_path"])
        except RuntimeError as exc:
            raise HTTPException(503, "Service de téléchargement indisponible") from exc
        if url:
            response.headers["Cache-Control"] = "no-store"
            return {"url": url}
    raise HTTPException(404, "Document indisponible")


def _detail_opportunite(reference: str, scope: str | None) -> dict[str, Any]:
    """Dossier complet d'une opportunité documentée, cadré sur l'entreprise."""
    sql = """
        SELECT s.reference, s.company_id, s.match_total, s.composantes, s.points_perdus,
               s.calcule_le, v.verdict, v.controles, v.justifications, v.risques_a_verifier,
               t.objet, t.organisme, t.secteur, t.region, t.montant_mad,
               t.caution_mad, t.date_remise, t.heure_remise, t.date_publication,
               t.heure_publication, t.source_url, t.reference_officielle, t.offer_type,
               t.extraction, f.statut_dossier, f.note
        FROM scores s
        LEFT JOIN verdicts v
          ON v.company_id = s.company_id AND v.reference = s.reference
         AND v.rendu_le >= s.calcule_le
        JOIN tenders t ON t.reference = s.reference
        LEFT JOIN favoris f
          ON f.company_id = s.company_id AND f.reference = s.reference
        WHERE s.reference = %s
          AND t.statut = 'ouvert'
          AND EXISTS (
            SELECT 1 FROM tender_documents d
            WHERE d.reference = t.reference AND (
              (d.statut IN ('extracted', 'ready') AND (
                COALESCE(d.char_count, 0) > 0 OR COALESCE(d.sections, 0) > 0
                OR NULLIF(btrim(COALESCE(d.extracted_text, '')), '') IS NOT NULL))
              OR EXISTS (SELECT 1 FROM cps_sections sec WHERE sec.document_id = d.id)
            )
          )
    """
    params: tuple = (reference,)
    if scope is not None:
        sql += " AND s.company_id = %s"
        params += (scope,)
    sql += " ORDER BY s.calcule_le DESC LIMIT 1"
    rows = db_cps.query(sql, params)
    if not rows:
        raise HTTPException(404, "Opportunité documentée introuvable")
    row = rows[0]
    company_id = scope or str(row["company_id"])
    opportunite = _opportunite(row)
    entreprise = db_cps.query(
        "SELECT nom FROM company_matching_profiles WHERE company_id = %s", (company_id,)
    )
    documents = db_cps.query(
        """
        SELECT id, doc_type, filename, statut, char_count, sections, extracted_text
        FROM tender_documents WHERE reference = %s
        ORDER BY (doc_type = 'CPS') DESC, char_count DESC NULLS LAST, id DESC LIMIT 8
        """, (reference,),
    )
    sections = db_cps.query(
        """
        SELECT sec.numero, sec.titre, sec.texte, sec.pages_section, d.filename
        FROM cps_sections sec
        JOIN tender_documents d ON d.id = sec.document_id
        WHERE d.reference = %s
        ORDER BY sec.id LIMIT 40
        """, (reference,),
    )
    justifications = _objet(row.get("justifications"), []) or []
    extraction = _objet(row.get("extraction"), {}) or {}
    points = list(opportunite["risks"])
    if extraction.get("penalty_text"):
        points.insert(0, "Pénalités mentionnées dans le dossier : " + str(extraction["penalty_text"])[:220])
    if extraction.get("visit"):
        points.insert(0, "Visite / reconnaissance mentionnée : " + str(extraction["visit"])[:220])
    return {
        "company": {"company_id": company_id,
                    "nom": entreprise[0]["nom"] if entreprise else "Entreprise"},
        "date": _jour(),
        "opportunity": opportunite,
        "analysis": {
            "summary": opportunite["advice"],
            "recommendations": opportunite["recommendations"],
            "advice": opportunite["advice"],
            "points_to_verify": points,
            "evidence": justifications,
        },
        "documents": [{
            "filename": d.get("filename") or "Document du dossier",
            "doc_type": d.get("doc_type") or "",
            "statut": d.get("statut") or "",
            "char_count": d.get("char_count") or 0,
            "sections": d.get("sections") or 0,
            "excerpt": (d.get("extracted_text") or "")[:900],
        } for d in documents],
        "sections": [{
            "numero": s.get("numero") or "",
            "titre": s.get("titre") or "",
            "texte": (s.get("texte") or "")[:700],
            "pages": s.get("pages_section") or "",
            "filename": s.get("filename") or "",
        } for s in sections],
    }


def _pdf_report(detail: dict[str, Any]) -> bytes:
    """Rapport PDF professionnel, généré à partir des données documentées."""
    from io import BytesIO

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import simpleSplit
    from reportlab.pdfgen import canvas

    vert = colors.HexColor("#17734f")
    encre = colors.HexColor("#12202b")
    gris = colors.HexColor("#66717a")
    buf = BytesIO()
    pdf = canvas.Canvas(buf, pagesize=A4)
    largeur, _ = A4
    y = 800

    def ecrire(texte: str, taille: int = 10, gras: bool = False,
               couleur=None, ecart: int = 14) -> None:
        nonlocal y
        Police = "Helvetica-Bold" if gras else "Helvetica"
        couleur = couleur or encre
        for ligne in simpleSplit(str(texte or ""), Police, taille, largeur - 90):
            if y < 60:
                pdf.showPage()
                y = 800
            pdf.setFont(Police, taille)
            pdf.setFillColor(couleur)
            pdf.drawString(45, y, ligne)
            y -= ecart

    def titre(text: str) -> None:
        nonlocal y
        y -= 6
        ecrire(text, 12, True, vert, 18)
        pdf.setStrokeColor(colors.HexColor("#d9e5de"))
        pdf.line(45, y + 4, largeur - 45, y + 4)
        y -= 10

    o = detail["opportunity"]
    a = detail["analysis"]
    ecrire("SOU9NA", 20, True, vert, 26)
    ecrire("Rapport d'analyse d'opportunite", 13, True, encre, 20)
    ecrire(f"Entreprise : {detail['company']['nom']}  |  Genere le {detail['date']}",
           9, False, gris, 22)

    titre("1. Resume executif")
    ecrire(o["title"]["fr"], 11, True, encre, 17)
    ecrire(f"Reference : {o['source_ref']}  |  Organisme : {o['buyer']['fr']}", 9, False, gris)
    ecrire(f"Score : {o['match_score']}/100  |  Verdict : {o['verdict'].upper()}  |  Confiance : {o['confidence']}",
           10, True, vert if o["verdict"] == "go" else encre)
    ecrire(f"Montant estimatif : {o['amount'] or 'non renseigne'} MAD  |  Caution : {o['guarantee'] or 'non renseignee'} MAD",
           9, False, gris)
    ecrire(f"Date de remise : {o['deadline']} {o.get('deadline_time') or ''}", 9, False, gris, 18)

    titre("2. Lecture Sou9na")
    ecrire(a["summary"], 10, False, encre, 16)

    titre("3. Points a verifier dans le dossier officiel")
    ecrire("Ces elements sont des actions de verification, pas des penalites affirmtees par Sou9na.",
           9, False, gris, 13)
    if a["points_to_verify"]:
        for i, point in enumerate(a["points_to_verify"], 1):
            ecrire(f"{i}. {point}", 9, False, encre, 13)
    else:
        ecrire("Aucun point bloquant identifie dans les pieces analysees.", 9, False, gris)

    titre("4. Recommandations")
    for i, rec in enumerate(a["recommendations"], 1):
        ecrire(f"{i}. {rec}", 9, False, encre, 14)

    titre("5. Conseil pratique")
    ecrire(a["advice"], 10, False, encre, 16)

    titre("6. Justifications et preuves")
    for item in a["evidence"][:10]:
        if isinstance(item, dict):
            ecrire(f"- {item.get('constat', '')} ({item.get('reference', '')})", 9, False, encre, 13)
        else:
            ecrire(f"- {item}", 9, False, encre, 13)

    titre("7. Documents et sections exploites")
    for doc in detail["documents"][:8]:
        ecrire(f"- {doc['filename']} ({doc['doc_type']}, {doc['char_count']} caracteres, {doc['sections']} sections)",
               9, False, encre, 13)
    for sec in detail["sections"][:12]:
        titre_sec = f"  {sec['numero']} {sec['titre']}".strip()
        ecrire(titre_sec or "  Section", 9, True, gris, 12)
        if sec["texte"]:
            ecrire(sec["texte"], 8, False, gris, 11)

    titre("8. Source officielle")
    ecrire(o.get("url") or "Lien disponible dans le tableau de bord Sou9na.", 9, False, encre)
    ecrire("Rapport genere uniquement a partir des offres documentees (extracted/ready ou CPS sections).",
           8, False, gris)
    pdf.save()
    return buf.getvalue()


@routeur.get("/opportunity-detail")
def opportunity_detail(reference: str = Query(min_length=1, max_length=512),
                       scope: str | None = Depends(_company_scope)) -> dict[str, Any]:
    return _detail_opportunite(reference, scope)


@routeur.get("/opportunity-report")
def opportunity_report(reference: str = Query(min_length=1, max_length=512),
                       scope: str | None = Depends(_company_scope)) -> Response:
    detail = _detail_opportunite(reference, scope)
    pdf = _pdf_report(detail)
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in reference)[:80]
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="sou9na-rapport-{safe}.pdf"'},
    )


@routeur.post("/opportunities/{reference}/save")
def save_opportunity(reference: str, company_id: str = Query(...),
                     saved: bool = Query(True),
                     scope: str | None = Depends(_company_scope)) -> dict[str, Any]:
    company_id = _require_company(company_id, scope)
    if saved:
        db_cps.execute(
            """
            INSERT INTO favoris (company_id, reference) VALUES (%s, %s)
            ON CONFLICT (company_id, reference) DO NOTHING
            """, (company_id, reference),
        )
    else:
        db_cps.execute(
            "DELETE FROM favoris WHERE company_id = %s AND reference = %s",
            (company_id, reference),
        )
    return {"reference": reference, "saved": saved}


@routeur.patch("/opportunities/{reference}")
def update_opportunity(reference: str, company_id: str = Query(...),
                       statut: str | None = None, note: str | None = None,
                       scope: str | None = Depends(_company_scope)) -> dict[str, Any]:
    company_id = _require_company(company_id, scope)
    statuts = ("a_etudier", "envoye", "gagne", "perdu")
    if statut is not None and statut not in statuts:
        raise HTTPException(400, "statut invalide")
    db_cps.execute(
        """
        INSERT INTO favoris (company_id, reference, statut_dossier, note)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (company_id, reference) DO UPDATE SET
          statut_dossier = COALESCE(EXCLUDED.statut_dossier, favoris.statut_dossier),
          note = COALESCE(EXCLUDED.note, favoris.note)
        """, (company_id, reference, statut or "a_etudier", note or ""),
    )
    return {"reference": reference, "statut": statut, "note": note}


@routeur.post("/companies/{company_id}/init", status_code=202)
def initialiser_company(company_id: str) -> dict[str, Any]:
    """Première analyse immédiate d'une entreprise inscrite en journée."""
    existe = db_cps.query(
        "SELECT 1 FROM company_matching_profiles WHERE company_id = %s", (company_id,)
    )
    if not existe:
        raise HTTPException(404, "entreprise introuvable")
    job = enqueue(company_id, "full", "full")
    mark_init(company_id, "running")
    return {
        "company_id": company_id,
        "init_status": "running",
        "job": job,
    }


def _concierge_agentic_d_abord() -> bool:
    return os.getenv("SOU9NA_AGENTIC_FIRST", "1").strip().lower() in (
        "1", "true", "oui", "yes")


@routeur.post("/chat")
def chat(message: str = Query(..., min_length=1),
         company_id: str = Query(...), date: str | None = None,
         scope: str | None = Depends(_company_scope)) -> dict[str, Any]:
    """Utilise le même moteur local que le service CONCIERGE A2A."""
    company_id = _require_company(company_id, scope)
    request_id = f"chat-{uuid.uuid4().hex[:12]}"
    reponse = repondre(message, company_id, date)
    reponse.setdefault("donnees", {})["source"] = "concierge_local"
    trace("concierge_flow", "ok", request_id, company_id, None,
          [{"agent": "concierge_local", "duration_s": 0.0}])
    return reponse


@routeur.post("/chat/visiteur")
def chat_visiteur(message: str = Query(..., min_length=1)) -> dict[str, Any]:
    return repondre(message, "visiteur")


def _chat_agentic_legacy(message: str, company_id: str,
                         date: str | None = None) -> dict[str, Any]:
    """CONCIERGE : flow Agentic d'abord, repli déterministe si erreur/timeout.

    Le repli reste local et cité : aucun message n'est envoyé depuis ce
    endpoint, la réponse est uniquement renvoyée à l'interface.
    """
    request_id = f"chat-{uuid.uuid4().hex[:12]}"
    detail = "flow Agentic non tenté"
    if _concierge_agentic_d_abord():
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] /
                                "03-agentic-ai" / "compagnon"))
        import agentic_flow

        try:
            # Le chat reste interactif : on ne laisse pas le timeout global
            # (900 s pour les jobs batch) bloquer l'interface.
            timeout = min(int(os.getenv("SOU9NA_AGENTIC_TIMEOUT", "90")), 120)
        except ValueError:
            timeout = 90
        try:
            ok, texte = agentic_flow.run_concierge_flow(
                company_id, message, date, timeout)
            if ok and texte.strip():
                trace("concierge_flow", "ok", request_id, company_id, None,
                      [{"agent": "agentic_concierge", "duration_s": 0.0,
                        "detail": texte[:400]}])
                return {
                    "texte": texte.strip(),
                    "citation": None,
                    "hitl": False,
                    "donnees": {"source": "flow_concierge"},
                }
            detail = texte or "réponse flow vide"
        except Exception as err:  # noqa: BLE001
            detail = f"{type(err).__name__}: {err}"
    reponse = repondre(message, company_id, date)
    reponse.setdefault("donnees", {})["source"] = "langgraph_fallback"
    reponse["donnees"]["detail_agentic"] = detail[:300]
    trace("concierge_flow", "fallback", request_id, company_id, detail[:240],
          [{"agent": "concierge_local", "duration_s": 0.0}])
    return reponse


@routeur.post("/prospects", status_code=201)
def creer_prospect(payload: dict[str, Any]) -> dict[str, Any]:
    """Formulaire d'accès anticipé de la landing — remplace le Supabase externe."""
    nom = str(payload.get("company_name") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    secteur = str(payload.get("sector") or "").strip()
    if not nom or not email or not secteur or "@" not in email:
        raise HTTPException(422, "nom, email et secteur requis")
    if not payload.get("consent"):
        raise HTTPException(422, "consentement loi 09-08 requis")
    whatsapp = str(payload.get("whatsapp") or "").strip() or None
    taille = str(payload.get("company_size") or "").strip() or None
    lang = "ar" if str(payload.get("lang") or "").lower().startswith("ar") else "fr"
    source = str(payload.get("source") or "landing").strip()[:60] or "landing"

    # Un contact public alimente désormais AUSSI la file d'attente admin :
    # prospects = traces marketing, waitlist = parcours invitation/onboarding.
    deja = db_cps.query(
        """SELECT 1 FROM prospects WHERE lower(email) = %s
           UNION ALL
           SELECT 1 FROM waitlist WHERE lower(email) = %s LIMIT 1""",
        (email, email),
    )
    if deja:
        raise HTTPException(409, "cet email est déjà enregistré")

    try:
        db_cps.execute(
            """
            INSERT INTO prospects (nom, email, whatsapp, secteur, taille,
                                   consentement_loi_09_08, honeypot)
            VALUES (%s, %s, %s, %s, %s, true, '')
            """,
            (nom, email, whatsapp, secteur, taille),
        )
    except UniqueViolation:
        raise HTTPException(409, "cet email est déjà enregistré")

    try:
        db_cps.execute(
            """
            INSERT INTO waitlist (company_name, email, whatsapp, sector,
                                  company_size, lang, consent, source, status)
            VALUES (%s, %s, %s, %s, %s, %s, true, %s, 'pending')
            """,
            (nom, email, whatsapp, secteur, taille, lang, source),
        )
    except UniqueViolation:
        # Course entre deux soumissions simultanées : le contact existe déjà,
        # on ne casse pas l'expérience utilisateur pour autant.
        pass

    return {"succes": True}
