# =====================================================================
# Sélection des documents pertinents pour la cible (TPME).
# La cible est déduite des profils clients actifs (entreprises / companies),
# avec des valeurs de repli et des surcharges configurables.
# =====================================================================
from __future__ import annotations

import re
from datetime import date
from typing import Any
from unicodedata import normalize as _unaccent

SECTOR_ALIASES: dict[str, set[str]] = {
    "informatique": {"informatique", "numerique", "digital", "logiciel", "it",
                     "cybersecurite", "telecom", "developpement", "systeme information"},
    "travaux": {"travaux", "btp", "construction", "rehabilitation", "genie civil",
                "batiment", "voirie", "amenagement", "maçonnerie"},
    "fournitures": {"fourniture", "fournitures", "equipement", "mobilier", "materiel",
                    "consommables"},
    "maintenance": {"maintenance", "entretien", "nettoyage", "gardiennage", "proprete"},
    "etudes": {"etude", "etudes", "conseil", "audit", "architecture", "formation",
               "ingenierie", "expertise"},
    "transport": {"transport", "logistique", "affretement", "vehicules"},
    "energie": {"energie", "electricite", "electrique"},
    "eau": {"eau", "assainissement"},
    "sante": {"sante", "medical", "sante medic", "hopital"},
    "agroalimentaire": {"agroalimentaire", "agriculture", "alimentaire", "cooperative"},
    "environnement": {"environnement", "dechets", "tri selectif"},
    "impression": {"impression", "imprimerie", "communication", "reprographie"},
    "hydrocarbures": {"hydrocarbures", "chimie"},
}

REGION_ALIASES: dict[str, set[str]] = {
    "casa-settat": {"casa", "casablanca", "settat", "mohammedia"},
    "rabat-sale-kenitra": {"rabat", "sale", "kenitra"},
    "tanger-tetouan-alhoceima": {"tanger", "tetouan", "alhoceima"},
    "souss-massa": {"agadir", "souss", "massa", "taroudant"},
    "marrakech-safi": {"marrakech", "safi", "essouira"},
    "fes-meknes": {"fes", "meknes"},
    "oriental": {"oujda", "nador"},
    "beni-mellal-khenifra": {"benimellal", "beni mellal", "khenifra"},
    "guelmim-oued-noun": {"guelmim", "tan tan"},
    "laayoune-sakia-el-hamra": {"laayoune", "sakia"},
    "dakhla-oued-ed-dahab": {"dakhla"},
}

FALLBACK_SECTORS = {
    "informatique", "travaux", "fournitures", "maintenance", "etudes",
    "transport", "energie", "eau", "sante", "agroalimentaire",
    "environnement", "impression",
}
FALLBACK_MAX_CAPACITY = 8_000_000.0  # profil démo le plus doté (Atlas Digital)


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = _unaccent("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def normalize_sector(value: Any) -> str:
    """Normalise un secteur (libellé FR du portail ou code client) en clé canonique."""
    text = _clean(value)
    if not text:
        return ""
    for canonical, aliases in SECTOR_ALIASES.items():
        if text == canonical or text in aliases:
            return canonical
        if any(re.search(rf"\b{re.escape(a)}\b", text) for a in aliases):
            return canonical
    return text


def normalize_region(value: Any) -> str:
    """Normalise une ville/région en clé de région officielle (ou texte brut)."""
    text = _clean(value)
    if not text:
        return ""
    for canonical, aliases in REGION_ALIASES.items():
        if text == canonical or text in aliases:
            return canonical
        if any(re.search(rf"\b{re.escape(a)}\b", text) for a in aliases):
            return canonical
    return text


def _parse_amount(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(str(value).strip().replace(" ", "").replace("\u00a0", "")
                     .replace(",", "."))
    except ValueError:
        return None


def build_envelope(profiles: list[dict[str, Any]], *,
                   sector_override: list[str] | None = None,
                   region_override: list[str] | None = None,
                   capacity_override: float | None = None) -> dict[str, Any]:
    """Construit l'enveloppe cible à partir des profils clients actifs."""
    sectors: set[str] = set()
    regions: set[str] = set()
    capacities: list[float] = []
    for p in profiles or []:
        s = normalize_sector(p.get("secteur") or p.get("sector"))
        if s:
            sectors.add(s)
        r = normalize_region(p.get("region"))
        if r:
            regions.add(r)
        c = _parse_amount(p.get("capacite_mad") or p.get("budget_max"))
        if c and c > 0:
            capacities.append(c)

    if sector_override:
        sectors = {normalize_sector(s) for s in sector_override if normalize_sector(s)}
    if region_override:
        regions = {normalize_region(r) for r in region_override if normalize_region(r)}
    if capacity_override:
        capacities = [capacity_override]

    return {
        "sectors": sectors or set(FALLBACK_SECTORS),
        "regions": regions,          # vide = pas de filtre région
        "max_capacity": max(capacities) if capacities else FALLBACK_MAX_CAPACITY,
        "profile_count": len(profiles or []),
    }


def _sector_matches(tender_sector: str, envelope_sectors: set[str]) -> bool:
    value = normalize_sector(tender_sector)
    # Secteur non renseigné/mal parsé par le portail : on ne rejette pas par excès.
    if not value or value in {"autre", "inconnu", "unknown"}:
        return True
    if value in envelope_sectors:
        return True
    return any(s in value or value in s for s in envelope_sectors if s)


def is_pertinent(tender: dict[str, Any], envelope: dict[str, Any], *,
                 today: date | None = None) -> dict[str, Any]:
    """Décision déterministe : document pertinent ou non, avec motif."""
    today = today or date.today()
    statut = str(tender.get("statut") or "").strip().lower()
    if statut in {"clos", "attribution", "termine", "archive"}:
        return {"ok": False, "reason": "statut_clos"}

    deadline = tender.get("date_remise")
    if deadline:
        try:
            if date.fromisoformat(str(deadline)[:10]) < today:
                return {"ok": False, "reason": "echeance_depassee"}
        except ValueError:
            pass

    if not _sector_matches(tender.get("secteur"), envelope["sectors"]):
        return {"ok": False, "reason": "secteur_hors_cible"}

    region = normalize_region(tender.get("region"))
    known_regions = set(REGION_ALIASES) | {
        alias for aliases in REGION_ALIASES.values() for alias in aliases
    }
    if envelope["regions"] and region and (region in known_regions):
        if region not in envelope["regions"]:
            return {"ok": False, "reason": "region_hors_cible"}

    amount = _parse_amount(tender.get("montant_mad"))
    cap = envelope.get("max_capacity")
    if amount is not None and cap and amount > cap:
        return {"ok": False, "reason": "montant_au_dessus_capacite"}

    return {"ok": True, "reason": "pertinent"}
