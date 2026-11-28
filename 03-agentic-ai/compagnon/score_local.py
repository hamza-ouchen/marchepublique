# =====================================================================
# COMPAGNON — Scorer déterministe local (production, 6000+ tenders)
#
# Pourquoi : un LLM ne peut pas restituer 6000 objets JSON de façon
# fiable (troncature, control chars, timeouts). Ce scorer fait le même
# calcul que le Prompt Template-KCyaz du flow, mais en Python pur :
#   - filtre DOMAINE (seulement les AO du secteur de l'entreprise)
#   - score déterministe (25/15/20/10/10/15/5), plafonné à 85 sans
#     qualifications déclarées : on n'invente pas de preuve documentaire.
#   - écriture DB idempotente (ON CONFLICT DO NOTHING)
#
# Le flow platform COMPAGNON reste disponible pour les petits runs /
# démos ; ce script est la voie de production pour la collecte complète.
# =====================================================================
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "02-backend"))
_env = ROOT / "02-backend" / ".env"
for _l in _env.read_text(encoding="utf-8").splitlines():
    _l = _l.strip()
    if _l and not _l.startswith("#") and "=" in _l:
        k, v = _l.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

DOMAIN_ALIASES = {
    "it": ["informatique", "numerique", "numérique", "logiciel",
           "cybersecurite", "cybersécurité", "telecom", "télécom",
           "digital", "developpement", "développement"],
    "btp": ["travaux", "construction", "rehabilitation", "réhabilitation",
            "batiment", "bâtiment", "architecture", "genie civil", "génie civil",
            "assainissement", "électricité", "electricite"],
    "construction": ["travaux", "construction", "rehabilitation", "réhabilitation",
                     "batiment", "bâtiment", "architecture", "genie civil",
                     "génie civil", "assainissement", "électricité", "electricite"],
    "fournitures": ["fourniture", "mobilier", "equipement", "équipement",
                    "materiel", "matériel", "consommables"],
    "maintenance": ["maintenance", "nettoyage", "gardiennage", "entretien",
                    "proprete", "propreté", "transport"],
    "transport": ["transport", "logistique"],
    "agriculture": ["agriculture", "agroalimentaire", "alimentaire", "agro"],
    "conseil": ["etude", "étude", "audit", "conseil", "formation",
                "traduction", "communication"],
    "mobilier": ["mobilier", "meuble", "amenagement"],
    "formation": ["formation", "enseignement", "pedagogie"],
    "gardiennage": ["gardiennage", "surveillance", "securite privee"],
    "nettoyage": ["nettoyage", "proprete", "hygiene"],
    "energie": ["energie", "electricite", "photovoltaïque", "eclairage"],
    "eau": ["eau", "assainissement", "hydraulique"],
    "sante": ["sante", "medical", "biomedical", "hospitalier", "pharmaceutique"],
    "impression": ["impression", "imprimerie", "reprographie", "communication"],
    "telecom": ["telecom", "telecommunication", "fibre optique"],
    "hydrocarbures": ["hydrocarbure", "carburant", "lubrifiant", "chimie"],
    "environnement": ["environnement", "dechet", "recyclage"],
    "communication": ["communication", "publicite", "evenementiel"],
    "audit": ["audit", "comptabilite", "commissariat aux comptes"],
    "traduction": ["traduction", "interpretariat"],
    "audiovisuel": ["photographie", "audiovisuel", "production video"],
    "architecture": ["architecture", "architecte", "maitrise d œuvre"],
    "rehabilitation": ["rehabilitation", "renovation", "restauration du batiment"],
    "logiciels": ["logiciel", "progiciel", "application informatique", "developpement logiciel"],
    "cybersecurite": ["cybersecurite", "securite informatique", "securite des systemes"],
    "restauration": ["alimentaire", "denree alimentaire", "restauration collective", "traiteur"],
    "fournitures scolaires": ["fournitures scolaires", "fourniture scolaire", "materiel pedagogique", "cartable", "manuel scolaire"],
}

for code, axe in {"informatique": "it", "travaux": "btp", "etudes": "conseil",
                  "agroalimentaire": "agriculture"}.items():
    DOMAIN_ALIASES[code] = DOMAIN_ALIASES[axe]


def _normalize_domain(value: str | None) -> str:
    word = unicodedata.normalize("NFKD", str(value or "").casefold())
    return " ".join(re.findall(r"[^\W_]+", "".join(c for c in word if not unicodedata.combining(c))))


def same_domain(company_secteur: str, tender_secteur: str, objet: str = "") -> bool:
    cs = _normalize_domain(company_secteur)
    ts = _normalize_domain(tender_secteur)
    if not cs:
        return False
    if cs == ts:
        return True
    if ts in {"", "services", "services et maintenance", "fournitures", "travaux",
              "btp", "conseil et etudes", "bons de commande", "autre"}:
        ts = f"{ts} {_normalize_domain(objet)}"
    aliases = {cs, *(_normalize_domain(a) for a in DOMAIN_ALIASES.get(cs, []))}
    return any(re.search(rf"\b{re.escape(alias)}(?:s|es)?\b", ts) for alias in aliases)


def load_company(cur, company_id: str) -> dict | None:
    statuts = [s.strip() for s in
               os.getenv("SOU9NA_COMPANY_STATUSES", "actif,essai").split(",")
               if s.strip()] or ["actif"]
    cur.execute('SELECT * FROM company_matching_profiles WHERE company_id = %s AND statut = ANY(%s)',
                (company_id, statuts))
    cols = [d[0] for d in cur.description]
    row = cur.fetchone()
    return dict(zip(cols, row)) if row else None


def load_tenders(cur, collect_date: str, all_open: bool = False) -> list[dict]:
    """Tenders à scorer.

    `all_open=True` sert au rattrapage d'une entreprise inscrite en cours de
    journée : on reprend TOUTES les offres ouvertes déjà collectées (pas
    seulement celles dont `date_collecte` vaut aujourd'hui), sans attendre le
    run du lendemain ni appeler la plateforme Agentic.
    """
    sql = """
        SELECT t.* FROM tenders t
        WHERE t.statut = %s
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
    """
    params: tuple = ("ouvert",)
    if not all_open:
        sql += ' AND date_collecte = %s'
        params += (collect_date,)
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def as_list(v) -> list:
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            return json.loads(v)
        except Exception:
            return []
    return []


def as_dict(v) -> dict:
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def _confidence(tender: dict) -> tuple[str, dict]:
    """Niveau de preuve documentaire — jamais deviné à partir du seul titre.

    `eleve` exige caution ET budget explicites, sans erreur d'enrichissement.
    Sans preuve, le score est plafonné et le GO reste impossible côté JUGE.
    """
    extraction = as_dict(tender.get("extraction"))
    signaux = as_list(extraction.get("signals"))
    caution = extraction.get("caution_mad") or None
    budget = extraction.get("budget_mad") or tender.get("montant_mad") or None
    erreur = extraction.get("error") or tender.get("enrich_error") or None

    if caution and budget and not erreur:
        return "eleve", {"reason": "caution_et_budget", "signals": sorted(map(str, signaux))}
    if caution or budget or extraction.get("penalties"):
        return "moyen", {"reason": "signal_partiel", "signals": sorted(map(str, signaux))}
    return "faible", {"reason": "donnees_manquantes", "signals": sorted(map(str, signaux))}


VERSION = "2.2.0-local"


def score(tender: dict, company: dict) -> dict | None:
    if not same_domain(company.get("secteur"), tender.get("secteur"), tender.get("objet") or ""):
        return None

    try:
        cap = float(company.get("capacite_mad") or 0)
        mont = float(tender.get("montant_mad") or 0)
        caution_mad = float(tender.get("caution_mad") or 0)
        delai = int(tender.get("delai_jours") or 0)
    except (ValueError, TypeError):
        cap = mont = caution_mad = 0.0
        delai = 0

    # Domaine déjà filtré en amont : socle constant, pas une preuve.
    secteur = 25
    region = 15 if tender.get("region") == company.get("region") else 0

    if mont <= 0:
        capacite = 10          # montant non déclaré → neutre, pas 20
    elif cap >= mont:
        capacite = 20
    elif cap >= mont * 0.8:
        capacite = 14
    elif cap >= mont * 0.5:
        capacite = 8
    else:
        capacite = 0

    if delai >= 60:
        delai_pts = 10
    elif delai >= 30:
        delai_pts = 6
    elif delai > 0:
        delai_pts = 2
    else:
        delai_pts = 3          # non renseigné → neutre

    if caution_mad <= 0 or cap <= 0:
        caution_pts = 5        # non renseigné → neutre
    elif caution_mad <= 0.1 * cap:
        caution_pts = 10
    elif caution_mad <= 0.3 * cap:
        caution_pts = 7
    elif caution_mad <= 0.5 * cap:
        caution_pts = 4
    else:
        caution_pts = 0

    req = set(map(str, as_list(tender.get("qualifications_exigees"))))
    ent = set(map(str, as_list(company.get("qualifications"))))
    if not req:
        qualifications = 0     # aucune preuve → 0, plafond réel 85/100
        qual_source = "non_renseigne"
    elif req.issubset(ent):
        qualifications = 15
        qual_source = "tender_metadata"
    elif req.intersection(ent):
        qualifications = 7
        qual_source = "tender_metadata_partiel"
    else:
        qualifications = 0
        qual_source = "tender_metadata"

    historique = 5
    for h in as_list(company.get("historique")):
        if isinstance(h, dict) and h.get("resultat") == "perdu":
            historique -= 2
    historique = max(historique, 0)

    total = secteur + region + capacite + caution_pts + delai_pts + qualifications + historique
    pertes = []
    if region == 0:
        pertes.append("region: mismatch (−15)")
    if capacite == 0:
        pertes.append("capacite: insuffisante (−20)")
    elif capacite < 20:
        pertes.append(f"capacite: partielle (−{20 - capacite})")
    if caution_pts < 10:
        pertes.append(f"caution: élevée (−{10 - caution_pts})")
    if delai_pts < 10:
        pertes.append(f"delai: tendu (−{10 - delai_pts})")
    if qualifications == 0:
        pertes.append("qualifications: non renseignées ou manquantes (−15)")
    elif qualifications < 15:
        pertes.append("qualifications: partiellement couvertes (−8)")
    if historique < 5:
        pertes.append("historique: marchés perdus")

    confiance, confiance_detail = _confidence(tender)
    if confiance == "faible":
        total = min(total, 65)
        pertes.append("preuves: caution/budget non confirmés (plafond 65)")
    elif confiance == "moyen":
        total = min(total, 72)
        pertes.append("preuves: signal partiel (plafond 72)")

    return {
        "reference": tender.get("reference"),
        "company_id": company.get("company_id"),
        "match_total": total,
        "composantes": {
            "secteur": secteur, "region": region, "capacite": capacite,
            "caution": caution_pts, "delai": delai_pts,
            "qualifications": qualifications, "historique": historique,
            "qualifications_source": qual_source,
            "confiance": confiance,
            "confiance_detail": confiance_detail,
        },
        "points_perdus": pertes,
        "algo_version": VERSION,
    }


def run_scoring(company_id: str, collect_date: str,
                all_open: bool = False) -> dict:
    """Outil interne COMPAGNON : score déterministe + écriture idempotente."""
    import psycopg

    conn = psycopg.connect(os.environ["DATABASE_URL"], prepare_threshold=None)
    try:
        with conn.cursor() as cur:
            company = load_company(cur, company_id)
            if not company:
                raise RuntimeError(f"entreprise {company_id} introuvable ou inactive")
            tenders = load_tenders(cur, collect_date, all_open=all_open)
            scores = []
            for tender in tenders:
                resultat = score(tender, company)
                if resultat:
                    scores.append(resultat)

            version = VERSION
            # Remplace l'ancienne version pour cette date : sans cela le JUGE
            # verrait deux scores par référence et écraserait le verdict 2 fois.
            cur.execute("""
                DELETE FROM scores
                WHERE company_id = %s AND calcule_le::date = %s
                  AND algo_version <> %s
            """, (company_id, collect_date, version))

            inserted = 0
            for item in scores:
                cur.execute("""
                    INSERT INTO scores
                      (reference, company_id, match_total, composantes, points_perdus, algo_version)
                    VALUES (%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (company_id, reference, algo_version) DO UPDATE SET
                      match_total = EXCLUDED.match_total,
                      composantes = EXCLUDED.composantes,
                      points_perdus = EXCLUDED.points_perdus,
                      calcule_le = now()
                """, (item["reference"], item["company_id"], item["match_total"],
                      json.dumps(item["composantes"]), json.dumps(item["points_perdus"]),
                      item["algo_version"]))
                inserted += 1
            conn.commit()

            cur.execute("SELECT count(*) FROM scores")
            total_scores = cur.fetchone()[0]
    finally:
        conn.close()

    return {
        "scores_ecrits": inserted,
        "scores_calcules": len(scores),
        "tenders_lus": len(tenders),
        "total_scores_db": total_scores,
        "algo_version": VERSION,
        "source": "local_fallback",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--company", default="EXPLEO-IT-001")
    ap.add_argument("--date", default=date.today().isoformat())
    args = ap.parse_args()

    resultat = run_scoring(args.company, args.date)
    print(f"Scores same-domain: {resultat['scores_calcules']} "
          f"sur {resultat['tenders_lus']} tenders")
    print(f"DB scores: +{resultat['scores_ecrits']}, "
          f"total={resultat['total_scores_db']}")


if __name__ == "__main__":
    main()
