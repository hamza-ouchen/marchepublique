# =====================================================================
# COMPAGNON — composition du digest (local, déterministe, zéro LLM).
# Lit scores + verdicts + tenders + entreprises, écrit digests (FR + AR).
# =====================================================================
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

_ROOT = Path(__file__).resolve().parents[2]
_ENV = _ROOT / "02-backend" / ".env"


def _load_env() -> None:
    if not _ENV.exists():
        return
    for line in _ENV.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_env()


def _conn():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row)


def _day_of_trial(essai_debut) -> int:
    if not essai_debut:
        return 1
    d0 = essai_debut if isinstance(essai_debut, date) else datetime.fromisoformat(str(essai_debut)).date()
    return max(1, (date.today() - d0).days + 1)


def _json_value(valeur: Any, defaut: Any) -> Any:
    if isinstance(valeur, (dict, list)):
        return valeur
    if isinstance(valeur, str):
        try:
            return json.loads(valeur)
        except Exception:
            return defaut
    return defaut


def composer(date_cible: str, company: str | None = None) -> dict[str, Any]:
    with _conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT company_id FROM scores WHERE calcule_le::date = %s"
            + (" AND company_id = %s" if company else ""),
            (date_cible, company) if company else (date_cible,),
        )
        companies = [r["company_id"] for r in cur.fetchall()]

    digests_composes = 0
    for company_id in companies:
        with _conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT s.reference, s.match_total, s.composantes, v.verdict, "
                "       v.controles, v.justifications, v.risques_a_verifier, "
                "       t.objet, t.date_remise, t.organisme "
                "FROM scores s "
                "LEFT JOIN verdicts v "
                "  ON v.company_id = s.company_id AND v.reference = s.reference "
                " AND v.rendu_le >= s.calcule_le "
                "JOIN tenders t ON t.reference = s.reference "
                "WHERE s.company_id = %s AND s.calcule_le::date = %s "
                "AND t.statut = 'ouvert' "
                "AND t.date_remise >= (now() AT TIME ZONE 'Africa/Casablanca')::date "
                "AND (t.heure_remise IS NULL OR t.date_remise + t.heure_remise > now() AT TIME ZONE 'Africa/Casablanca') "
                "AND EXISTS (SELECT 1 FROM tender_documents d "
                "  WHERE d.reference = t.reference AND d.statut IN ('extracted', 'ready') "
                "  AND (d.char_count > 0 OR d.sections > 0 "
                "       OR NULLIF(btrim(d.extracted_text), '') IS NOT NULL)) "
                "ORDER BY s.match_total DESC",
                (company_id, date_cible),
            )
            rows = cur.fetchall()

            cur.execute("SELECT * FROM company_matching_profiles WHERE company_id = %s", (company_id,))
            ent = cur.fetchone()

        top = []
        top_ar = []
        counts = {"go": 0, "a_etudier": 0, "no_go": 0}
        for r in rows[:5]:
            verdict = r.get("verdict") or "A_ETUDIER"
            if verdict == "GO":
                counts["go"] += 1
            elif verdict == "A_ETUDIER":
                counts["a_etudier"] += 1
            elif verdict == "NO_GO":
                counts["no_go"] += 1

            controles = _json_value(r.get("controles"), {})
            risques = _json_value(r.get("risques_a_verifier"), [])
            justifications = _json_value(r.get("justifications"), [])
            citation = justifications[0] if justifications and isinstance(justifications[0], dict) else {}
            ligne = {
                "reference": r["reference"],
                "objet": r.get("objet") or "",
                "organisme": r.get("organisme") or "",
                "match": r["match_total"],
                "remise": str(r["date_remise"]) if r.get("date_remise") else "",
                "verdict": verdict,
                "confiance": controles.get("_confiance", "faible"),
                "source_preuve": controles.get("_source_preuve", "metadata_seul"),
                "documents_exploites": controles.get("_documents_exploites", 0),
                "risques": risques if isinstance(risques, list) else [],
                "citation": {
                    "constat": citation.get("constat", ""),
                    "reference": citation.get("reference", ""),
                    "article": citation.get("article", ""),
                    "pages": citation.get("pages", ""),
                },
            }
            top.append(ligne)
            top_ar.append(ligne | {
                "verdict": {"GO": "مقبول", "A_ETUDIER": "للدراسة", "NO_GO": "مرفوض"}.get(verdict, verdict),
            })

        jour_essai = _day_of_trial(ent.get("essai_debut")) if ent else 1
        bandeau = f"essai jour {jour_essai} sur 14"

        contenu_fr = {
            "titre": f"Vos opportunités du {date_cible}",
            "top_matchs": top,
            "verdicts": counts,
            "bandeau": bandeau,
            "lien_dashboard": os.getenv("SOU9NA_DASHBOARD_URL", "http://localhost:3000/dashboard"),
        }
        contenu_ar = {
            "titre": f"فرصكم ديال {date_cible}",
            "top_matchs": top_ar,
            "verdicts": counts,
            "bandeau": f"اليوم {jour_essai} من 14",
            "lien_dashboard": os.getenv("SOU9NA_DASHBOARD_URL", "http://localhost:3000/dashboard"),
        }

        with _conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO digests (company_id, jour, contenu_fr, contenu_ar, bandeau, statut_envoi, envoye_le, digest_date, content, channels)
                VALUES (%s, %s, %s::jsonb, %s::jsonb, %s, 'compose', NULL, %s, %s, %s::jsonb)
                ON CONFLICT (company_id, jour) DO UPDATE SET
                  contenu_fr = EXCLUDED.contenu_fr,
                  contenu_ar = EXCLUDED.contenu_ar,
                  bandeau = EXCLUDED.bandeau,
                  digest_date = EXCLUDED.digest_date,
                  content = EXCLUDED.content,
                  channels = EXCLUDED.channels,
                  statut_envoi = 'compose',
                  envoye_le = NULL
                WHERE digests.statut_envoi <> 'envoye'
                """,
                (company_id, date_cible, json.dumps(contenu_fr, ensure_ascii=False),
                 json.dumps(contenu_ar, ensure_ascii=False), bandeau, date_cible,
                 json.dumps(contenu_fr, ensure_ascii=False), json.dumps(["dashboard"])),
            )
            conn.commit()
        digests_composes += 1

    return {"date": date_cible, "digests_composes": digests_composes, "bandeau": bandeau if companies else "aucun"}


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    print(json.dumps(composer(d), indent=2, ensure_ascii=False))
