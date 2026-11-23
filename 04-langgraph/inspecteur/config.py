# =====================================================================
# Configuration de la collecte de documents (CPS/DCE).
# Tout est pilotable par variables d'environnement (.env, jamais commité).
# =====================================================================
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]  # racine du dépôt marchepublique

# L'option --env-file du CLI est appliquée avant l'import de ce module.
_env_file = os.getenv("ENV_FILE")
if _env_file:
    load_dotenv(_env_file, override=False)
else:
    load_dotenv(_ROOT / ".env", override=False)
    load_dotenv(_HERE / ".env", override=False)


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "").strip() or default)
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw in {"1", "true", "yes", "on", "oui"}


def _list(name: str) -> list[str]:
    return [v.strip() for v in os.getenv(name, "").split(",") if v.strip()]


DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_SERVICE_KEY = (os.getenv("SUPABASE_SERVICE_KEY", "")
                        or os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")).strip()

PORTAL_BASE = os.getenv("PORTAL_BASE", "https://www.marchespublics.gov.ma").strip().rstrip("/")
USER_AGENT = os.getenv(
    "PORTAL_USER_AGENT",
    "Mozilla/5.0 (compatible; Sou9naBot/1.0; document collector; +https://soukna.ma)",
)
REQUEST_TIMEOUT_S = _float("PORTAL_TIMEOUT_S", 10.0)
PORTAL_DELAY_S = _float("PORTAL_DELAY_S", 1.0)
MAX_CONSECUTIVE_FAILURES = _int("CPS_MAX_CONSECUTIVE_FAILURES", 3)
# Seul le portail national est exploitable sans navigateur JS.
ALLOWED_HOSTS = _list("CPS_ALLOWED_HOSTS") or ["www.marchespublics.gov.ma"]

# Garde-fous — free tier Supabase Storage (500 Mo) : valeurs volontairement basses.
MAX_PDF_BYTES = _int("CPS_MAX_PDF_BYTES", 5 * 1024 * 1024)  # 5 Mo / PDF
MAX_PAGES = _int("CPS_MAX_PAGES", 60)
MAX_DOCS = _int("CPS_MAX_DOCS", 30)                          # docs / exécution
TOTAL_BUDGET_BYTES = _int("CPS_TOTAL_BUDGET_BYTES", 100 * 1024 * 1024)  # 100 Mo
STORE_ORIGINALS = _bool("CPS_STORE_ORIGINALS", False)        # défaut : texte seul en DB
BUCKET = os.getenv("CPS_BUCKET", "cps-originaux").strip()

# Surcharges optionnelles de la cible (sinon déduite des profils actifs).
# OCR (PDF scannés) : binaire tesseract + données 'fra' (non commitées).
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "").strip()
TESSDATA_DIR = os.getenv("TESSDATA_DIR", str(_HERE / "tessdata")).strip()
OCR_LANG = os.getenv("OCR_LANG", "fra").strip()
OCR_DPI = _int("OCR_DPI", 200)

SECTOR_OVERRIDE = _list("CPS_SECTORS")
REGION_OVERRIDE = _list("CPS_REGIONS")
CAPACITY_OVERRIDE = _int("CPS_MAX_CAPACITY_MAD", 0) or None

# -----------------------------------------------------------------------
# Job complet (« full job ») : offres + statuts + documents + champs
# -----------------------------------------------------------------------

# Repli aomaroc (uniquement si le portail ne livre pas le dossier).
AO_BASE = os.getenv("AO_BASE", "https://www.aomaroc.com").strip().rstrip("/")
AO_ENABLED = _bool("AO_FALLBACK_ENABLED", True)

# Identité déclarée au portail pour la demande de téléchargement DCE
# (formulaire obligatoire avant completeDownload).
DCE_FORM = {
    "nom": os.getenv("DCE_NOM", "Soukna").strip(),
    "prenom": os.getenv("DCE_PRENOM", "Bot").strip(),
    "email": os.getenv("DCE_EMAIL", "contact@soukna.ma").strip(),
    "raisonSocial": os.getenv("DCE_RAISON_SOCIAL", "Soukna").strip(),
    "ICE": os.getenv("DCE_ICE", "0023456780000AB").strip(),
    "address": os.getenv("DCE_ADRESSE", "Casablanca").strip(),
    "ville": os.getenv("DCE_VILLE", "Casablanca").strip(),
    "cp": os.getenv("DCE_CP", "20000").strip(),
    "tel": os.getenv("DCE_TEL", "0600000000").strip(),
}

# Marche du listing : état de reprise + collecte brute pour ré-audit
WALK_STATE_PATH = Path(os.getenv(
    "WALK_STATE_PATH", str(_HERE / "portal_walk_state.json")))
AUDIT_MAP_PATH = Path(os.getenv(
    "AUDIT_MAP_PATH", str(_HERE / "audit_map.jsonl")))
WALK_MINUTES = _float("WALK_MINUTES", 10.0)
AUDIT_MINUTES = _float("AUDIT_MINUTES", 4.0)
AUDIT_WORKERS = _int("AUDIT_WORKERS", 6)
DOCS_MINUTES = _float("DOCS_MINUTES", 8.0)
FIELDS_MINUTES = _float("FIELDS_MINUTES", 5.0)

# Dossier DCE : ZIP -> PDFs (récursifs, dédoublonnés), au plus N par offre
MAX_DOCS_PER_TENDER = _int("CPS_MAX_DOCS_PER_TENDER", 12)
MAX_ZIP_BYTES = _int("CPS_MAX_ZIP_BYTES", 80 * 1024 * 1024)

# Offres terminées : supprimées de 'tenders' (documents/scores/verdicts
# partent avec elles) au lieu d'être marquées.
DELETE_FINISHED_OFFERS = _bool("DELETE_FINISHED_OFFERS", True)
