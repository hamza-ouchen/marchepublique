# =====================================================================
# JUGE — verdicts GO / A_ETUDIER / NO_GO (déterministe, zéro LLM).
# Lit les scores du jour + tenders + entreprises, écrit verdicts.
# =====================================================================
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db_juge


def _qualifications_ok(entreprise: dict[str, Any], tender: dict[str, Any]) -> tuple[str, list[str]]:
    exigees = set(tender.get("qualifications_exigees") or [])
    detenues = set(entreprise.get("qualifications") or [])
    if not exigees:
        return "inconnu", []
    if not detenues:
        return "inconnu", sorted(exigees)
    manquantes = exigees - detenues
    if not manquantes:
        return "ok", []
    if manquantes == exigees:
        return "ko", sorted(manquantes)
    return "risque", sorted(manquantes)


def _dict(valeur: Any) -> dict[str, Any]:
    if isinstance(valeur, dict):
        return valeur
    if isinstance(valeur, str):
        try:
            charge = json.loads(valeur)
            return charge if isinstance(charge, dict) else {}
        except Exception:
            return {}
    return {}


def _nombre(valeur: Any) -> float | None:
    """Retourne un nombre exploitable, ou None si la donnée est absente.

    Une valeur nulle/vide n'est jamais interprétée comme 0 : dans un avis,
    cela veut dire « non extrait », pas « gratuit ».
    """
    if valeur is None or valeur == "":
        return None
    try:
        nombre = float(valeur)
    except (TypeError, ValueError):
        return None
    return nombre if nombre > 0 else None


def _mad(valeur: Any) -> str:
    nombre = _nombre(valeur)
    return "inconnu" if nombre is None else f"{nombre:,.0f} MAD"


def _jours(valeur: Any) -> str:
    nombre = _nombre(valeur)
    return "inconnu" if nombre is None else f"{nombre:,.0f}"


def _confiance(tender: dict[str, Any], score: dict[str, Any]) -> str:
    """La confiance vient du score COMPAGNON, avec repli sur l'extraction."""
    composantes = _dict(score.get("composantes"))
    niveau = composantes.get("confiance")
    if niveau in ("eleve", "moyen", "faible"):
        return str(niveau)
    extraction = _dict(tender.get("extraction"))
    caution = _nombre(extraction.get("caution_mad"))
    budget = _nombre(extraction.get("budget_mad"))
    if budget is None:
        budget = _nombre(tender.get("montant_mad"))
    erreur = extraction.get("error") or tender.get("enrich_error")
    if caution is not None and budget is not None and not erreur:
        return "eleve"
    if caution is not None or budget is not None or extraction.get("penalties"):
        return "moyen"
    return "faible"


def juger(date_cible: str, company: str | None = None) -> dict[str, Any]:
    """Produit les verdicts pour tous les scores du jour. Retourne un rapport."""
    scores = db_juge.scores_for_date(date_cible, company)
    docs = db_juge.doc_index()
    go = a_et = no_go = 0
    avec_doc = sans_doc = 0
    confiances = {"eleve": 0, "moyen": 0, "faible": 0}
    ecrits = 0
    details = []

    for sc in scores:
        company_id = sc["company_id"]
        reference = sc["reference"]
        tender = db_juge.tender_by_reference(reference)
        entreprise = db_juge.entreprise_by_id(company_id)
        if not tender or not entreprise:
            continue

        preuve = docs.get(reference) or {}
        has_doc = bool(preuve.get("has_doc"))
        nb_documents = int(preuve.get("nb_documents") or 0)
        nb_sections = int(preuve.get("nb_sections") or 0)

        # --- Contrôle 1 : caution vs capacité ---
        caution = _nombre(tender.get("caution_mad"))
        capacite = _nombre(entreprise.get("capacite_mad"))
        if capacite is None or capacite <= 0:
            ctrl_caution = "inconnu"
        elif caution is None or caution <= 0:
            ctrl_caution = "inconnu"
        elif caution > capacite:
            ctrl_caution = "ko"
        elif caution > 0.5 * capacite:
            ctrl_caution = "risque"
        else:
            ctrl_caution = "ok"

        # --- Contrôle 2 : ICE / attestations (proxy : montant vs capacité) ---
        montant = _nombre(tender.get("montant_mad"))
        if capacite is None or capacite <= 0 or montant is None or montant <= 0:
            ctrl_ice = "inconnu"
        elif montant > 10 * capacite:
            ctrl_ice = "risque"
        else:
            ctrl_ice = "ok"

        # --- Contrôle 3 : qualifications ---
        ctrl_qual, manquantes = _qualifications_ok(entreprise, tender)

        # --- Contrôle 4 : délai atteignable ---
        delai = _nombre(tender.get("delai_jours"))
        if delai is None or delai <= 0:
            ctrl_delai = "inconnu"
        elif delai < 15:
            ctrl_delai = "ko"
        elif delai < 60:
            ctrl_delai = "risque"
        else:
            ctrl_delai = "ok"

        controles = {
            "caution_vs_capacite": ctrl_caution,
            "ice_attestations": ctrl_ice,
            "qualifications": ctrl_qual,
            "delai_atteignable": ctrl_delai,
        }

        # --- Verdict : garde-fous additivefs, jamais de GO sans preuve ---
        score = int(sc.get("match_total") or 0)
        confiance = _confiance(tender, sc)
        if not has_doc:
            confiance = "faible"       # aucun document -> jamais "eleve"

        bloquant = any(valeur == "ko" for valeur in controles.values()) or score < 45
        if bloquant:
            verdict = "NO_GO"
        elif (
            not has_doc
            or score < 75
            or confiance != "eleve"
            or {"risque", "inconnu"}.intersection(controles.values())
        ):
            verdict = "A_ETUDIER"
        else:
            verdict = "GO"

        source_preuve = "document" if has_doc else "metadata_seul"
        confiances[confiance] += 1

        controles.update({
            "_score": score,
            "_confiance": confiance,
            "_source_preuve": source_preuve,
            "_documents_exploites": nb_documents,
            "_sections_exploitees": nb_sections,
        })

        # --- Justifications (≥ 1 citation) ---
        justifications = [{
            "constat": f"caution {_mad(caution)} vs capacité {_mad(capacite)}",
            "reference": "décret 2-22-431, art. 12",
        }]
        if ctrl_caution == "inconnu":
            justifications.append({
                "constat": "Caution ou capacité financière non vérifiée",
                "reference": "avis officiel et décret 2-22-431, art. 12",
            })
        elif ctrl_caution != "ok":
            justifications.append({
                "constat": "Caution disproportionnée par rapport à la capacité financière",
                "reference": "décret 2-22-431, art. 12",
            })
        if ctrl_ice == "inconnu":
            justifications.append({
                "constat": "Montant estimatif ou attestation de capacité non vérifié",
                "reference": "avis officiel, art. montant et attestations",
            })
        elif ctrl_ice == "risque":
            justifications.append({
                "constat": f"montant {_mad(montant)} vs capacité {_mad(capacite)} — effort financier élevé",
                "reference": "avis officiel, art. montant et attestations",
            })
        if not has_doc:
            justifications.append({
                "constat": "Aucun document exploitable pour ce dossier",
                "reference": "dossier officiel à télécharger (CPS / CCTP / additifs)",
            })
        if ctrl_qual == "inconnu":
            evidence = db_juge.qualification_section(reference)
            justification = {"constat": "Exigences de qualification non vérifiées",
                             "reference": "Dossier officiel à vérifier"}
            if evidence:
                justification.update({
                    "reference": evidence["filename"] or "Document du dossier",
                    "article": evidence["numero"],
                    "pages": evidence["pages_section"],
                    "source_url": evidence["source_url"],
                })
            justifications.append(justification)
        elif ctrl_qual != "ok":
            justifications.append({
                "constat": f"qualifications manquantes : {', '.join(manquantes)}",
                "reference": "avis officiel, art. qualifications",
            })
        if ctrl_delai == "inconnu":
            justifications.append({
                "constat": "Délai d'exécution non renseigné",
                "reference": "avis officiel et CCTP du dossier",
            })
        elif ctrl_delai != "ok":
            justifications.append({
                "constat": f"délai {_jours(delai)} jours — à vérifier",
                "reference": "cctp du dossier officiel",
            })

        # --- Risques (≥ 3 si A_ETUDIER) ---
        risques: list[str] = []
        extraction = _dict(tender.get("extraction"))
        if verdict == "A_ETUDIER":
            if not has_doc:
                risques.append("télécharger et analyser le dossier officiel (CPS / CCTP / additifs) avant décision")
            if ctrl_caution == "inconnu":
                risques.append("confirmer la caution et la capacité financière dans l'avis et les documents officiels")
            if ctrl_caution == "risque":
                risques.append("confirmer la caution provisoire auprès de la banque")
            if ctrl_ice == "inconnu":
                risques.append("confirmer le montant estimatif et l'attestation de capacité dans le dossier officiel")
            if ctrl_ice == "risque":
                risques.append("confirmer la capacité financière avec un partenaire")
            if ctrl_qual == "inconnu":
                risques.append("vérifier les qualifications dans le CPS et les additifs")
            if ctrl_qual == "risque":
                risques.append(f"obtenir l'attestation manquante ({', '.join(manquantes)}) avant la remise")
            if ctrl_delai == "inconnu":
                risques.append("vérifier le délai d'exécution dans l'avis officiel et le CCTP")
            if ctrl_delai == "risque":
                risques.append("vérifier la faisabilité du planning avec le conducteur de travaux")
            if extraction.get("penalty_text"):
                risques.append("pénalités de retard mentionnées : " + str(extraction["penalty_text"])[:160])
            if extraction.get("visit"):
                risques.append("visite ou reconnaissance des lieux mentionnée : " + str(extraction["visit"])[:160])
            if _nombre(extraction.get("caution_mad")) is None:
                risques.append("caution non confirmée dans le dossier officiel")
            if _nombre(extraction.get("budget_mad")) is None:
                risques.append("budget estimatif non confirmé dans le dossier officiel")
            for repli in (
                "vérifier le détail des lots et sous-lots avant dépôt",
                "contrôler les pièces administratives exigées par l'avis",
                "vérifier les conditions de remise et la date limite dans le dossier officiel",
            ):
                if len(risques) >= 3:
                    break
                if repli not in risques:
                    risques.append(repli)

        db_juge.upsert_verdict({
            "company_id": company_id,
            "reference": reference,
            "verdict": verdict,
            "controles": controles,
            "justifications": justifications,
            "risques_a_verifier": risques,
        })
        ecrits += 1
        if has_doc:
            avec_doc += 1
        else:
            sans_doc += 1
        if verdict == "GO":
            go += 1
        elif verdict == "A_ETUDIER":
            a_et += 1
        else:
            no_go += 1
        details.append({
            "company_id": company_id,
            "reference": reference,
            "verdict": verdict,
            "confiance": confiance,
            "source_preuve": source_preuve,
        })

    db_juge.commit_verdicts()

    return {
        "date": date_cible,
        "verdicts_ecrits": ecrits,
        "go": go,
        "a_etudier": a_et,
        "no_go": no_go,
        "avec_document": avec_doc,
        "sans_document": sans_doc,
        "confiances": confiances,
        "details": details,
    }


if __name__ == "__main__":
    d = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    company = sys.argv[2] if len(sys.argv) > 2 else None
    print(json.dumps(juger(d, company), indent=2, ensure_ascii=False))
