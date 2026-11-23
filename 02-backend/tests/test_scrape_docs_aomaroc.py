# =====================================================================
# Tests scrape_docs_aomaroc (déterministes, sans réseau, sans DB).
# =====================================================================
from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import scrape_docs_aomaroc as sda


# --- parse_portal_keys -------------------------------------------------

def test_parse_portal_keys_ok():
    url = ("https://www.marchespublics.gov.ma/?page=entreprise.EntrepriseDetails"
           "Consultation&refConsultation=1052604&orgAcronyme=p8x&code=&retraits")
    assert sda.parse_portal_keys(url) == ("1052604", "p8x")


def test_parse_portal_keys_escapes():
    url = ("https://www.marchespublics.gov.ma/?page=entreprise.EntrepriseDetails"
           "Consultation&refConsultation=10006456&orgAcronyme=x1%2Fy")
    assert sda.parse_portal_keys(url) == ("10006456", "x1/y")


@pytest.mark.parametrize("url", [
    "", None,
    "https://example.com/test",
    "https://www.marchespublics.gov.ma/?page=x&refConsultation=123",   # sans org
    "https://www.marchespublics.gov.ma/?page=x&orgAcronyme=p8x",       # sans ref
])
def test_parse_portal_keys_none(url):
    assert sda.parse_portal_keys(url or "") is None


# --- sanitize_path_part ------------------------------------------------

def test_sanitize_accents_ascii():
    assert sda.sanitize_path_part("Avis_FR_Aménagements_des_pistes.pdf") == \
        "Avis_FR_Amenagements_des_pistes.pdf"


def test_sanitize_spaces_and_slashes():
    # espaces -> '_', caractères interdits (/, parenthèses...) supprimés
    assert sda.sanitize_path_part("R C Travaux/2026 école.pdf") == \
        "R_C_Travaux2026_ecole.pdf"


def test_sanitize_fallback():
    assert sda.sanitize_path_part("###") == "document.pdf"


# --- classify_doc_type -------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("CPS travaux Ecole AL FARAH-modif.pdf", "CPS"),
    ("cahier des prescriptions spéciales.pdf", "CPS"),
    ("R C Travaux Ecole AL FARAH.pdf", "DCE"),
    ("RC_CC_SIDI_KASEM_TECH11.pdf", "DCE"),
    ("Avis 66-INV-2026 FR.pdf", "AVIS"),
    ("Avis rectificatif 66-INV-2026 Fr.pdf", "ADDITIF"),
    ("Additif n°2.pdf", "ADDITIF"),
    ("BORDEREAU ESTIMATIF.pdf", "DCE"),   # défaut
])
def test_classify_doc_type(name, expected):
    assert sda.classify_doc_type(name) == expected


# --- pdfs_from_zip -----------------------------------------------------

def _zip_bytes(entries: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in entries.items():
            zf.writestr(name, data)
    return buf.getvalue()


def test_pdfs_from_zip_orders_cps_first():
    # Octets distincts par fichier (sinon le dédoublonnage sha256 ne garde
    # qu'un seul exemplaire).
    pdfs = {
        "Avis FR.pdf": b"%PDF-1.4 avis" + b"a" * 2048,
        "RC consultation.pdf": b"%PDF-1.4 rc" + b"r" * 2048,
        "CPS principal.pdf": b"%PDF-1.4 cps" + b"c" * 2048,
    }
    data = _zip_bytes({**pdfs, "ACTE ENGAGEMENT.docx": b"not a pdf"})
    names = [n for n, _ in sda.pdfs_from_zip(data)]
    assert names == ["CPS principal.pdf", "RC consultation.pdf", "Avis FR.pdf"]


def test_pdfs_from_zip_rejects_fake_pdf_and_empty():
    data = _zip_bytes({
        "vide.pdf": b"",                    # < 1024 octets
        "faux.pdf": b"PK-3.4 not pdf",      # magic absent
        "bon.pdf": b"%PDF-1.4" + b"x" * 2000,
    })
    names = [n for n, _ in sda.pdfs_from_zip(data)]
    assert names == ["bon.pdf"]


def test_pdfs_from_zip_bad_zip():
    assert sda.pdfs_from_zip(b"not a zip at all") == []


def test_pdfs_from_zip_recurses_nested_zip():
    pdf = b"%PDF-1.4" + b"x" * 2048
    inner = _zip_bytes({"DCE CPS dossier.pdf": pdf})
    outer = _zip_bytes({"Avis.docx": b"docx", "DCE AO VF.zip": inner})
    names = [n for n, _ in sda.pdfs_from_zip(outer)]
    # le docx est ignoré, le PDF du ZIP imbriqué est extrait
    assert names == ["DCE CPS dossier.pdf"]


def test_pdfs_from_zip_ignores_subdirs():
    data = _zip_bytes({
        "sous/rep/CPS x.pdf": b"%PDF-1.4 cps" + b"c" * 2048,
        "RACINE.pdf": b"%PDF-1.4 racine" + b"r" * 2048,
    })
    names = [n for n, _ in sda.pdfs_from_zip(data)]
    # basename seul (sous-dossiers aplatis) ; CPS en premier (priorité)
    assert names[0] == "CPS x.pdf"
    assert "RACINE.pdf" in names
