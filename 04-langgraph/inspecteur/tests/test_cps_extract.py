from __future__ import annotations

from pathlib import Path

from inspecteur import cps_extract

FIXTURE = Path(__file__).parent / "fixtures" / "cps_fixture.pdf"


def test_fixture_et_extraction():
    assert FIXTURE.exists()
    info = cps_extract.extract_text(FIXTURE.read_bytes())
    assert info["extraction"] == "pypdf"
    assert info["pages"] == 1
    assert info["char_count"] >= 100
    assert len(info["sha256"]) == 64


def test_sections():
    info = cps_extract.extract_text(FIXTURE.read_bytes())
    sections = cps_extract.split_into_sections(info["text"])
    assert len(sections) == 5
    assert [s["section_no"] for s in sections] == list(range(1, 6))
    assert any("Article 1" in (s["titre"] or "") for s in sections)


def test_texte_vide():
    assert cps_extract.split_into_sections("") == []
    assert len(cps_extract.split_into_sections("Texte libre sans titre.")) == 1


def test_ocr_pdf_image_only():
    """Un PDF scanné (sans couche texte) est extrait par tesseract/fra."""
    import pymupdf

    src = pymupdf.open(str(FIXTURE))
    pix = src[0].get_pixmap(dpi=150)
    out = pymupdf.open()
    page = out.new_page(width=pix.width, height=pix.height)
    page.insert_image(page.rect, pixmap=pix)
    data = out.tobytes()
    src.close()
    out.close()

    info = cps_extract.extract_text(data)
    assert info["extraction"] == "ocr_tesseract_fra_best"
    assert info["char_count"] >= 100
    assert "Article 1" in info["text"]
