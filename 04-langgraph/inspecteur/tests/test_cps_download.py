from __future__ import annotations

import pytest
import requests

from inspecteur import cps_download


HTML = """
<html><body>
  <a href="/documents/telecharger?ref=99">Cahier des prescriptions spéciales (CPS)</a>
  <a href="/static/avis.pdf">Avis de consultation</a>
  <a href="javascript:void(0)">Détail</a>
</body></html>
"""


def test_find_pdf_links_priorise_cps():
    links = cps_download.find_pdf_links("https://portail.ma/avis/123", HTML)
    # Seuls les liens directs (.pdf ou idAvis=nombre) sont conservés ;
    # le lien 'telecharger?ref=99' (formulaire) est exclu.
    assert len(links) == 1
    assert links[0].endswith("/static/avis.pdf")


def test_nav_links_exclus():
    html = """
    <a href="?page=entreprise.EntrepriseAdvancedSearch&amp;AvisAttribution#2">
      Tous les résultats définitifs</a>
    <a href="index.php?page=entreprise.EntrepriseDownloadAvisJAL&amp;idAvis=541043">
      Fichier joint - Avis complémentaire</a>
    """
    links = cps_download.find_pdf_links("https://www.marchespublics.gov.ma/?id=1", html)
    assert len(links) == 1
    assert "EntrepriseDownloadAvisJAL" in links[0]
    assert "AvisAttribution" not in links[0]


def test_liens_sans_fichier_exclus():
    html = """
    <a href="index.php?page=entreprise.EntrepriseDownloadAvisJAL&amp;idAvis="></a>
    <a href="index.php?page=entreprise.EntrepriseDemandeTelechargementDce&amp;id=1">
      Dossier de consultation</a>
    <a href="index.php?page=entreprise.EntrepriseDownloadAvisJAL&amp;idAvis=541043">
      Fichier joint</a>
    """
    links = cps_download.find_pdf_links("https://www.marchespublics.gov.ma/?id=1", html)
    assert len(links) == 1
    assert "idAvis=541043" in links[0]


class FakeResponse:
    def __init__(self, data: bytes, text: str = ""):
        self.data = data
        self.text = text
        self.closed = False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        yield self.data

    def close(self):
        self.closed = True


def test_download_pdf(monkeypatch):
    fake = FakeResponse(b"%PDF-1.4 contenu de test")
    monkeypatch.setattr(cps_download.requests, "get", lambda *a, **k: fake)
    data = cps_download.download_pdf("https://portail.ma/f.pdf", max_bytes=1000)
    assert data.startswith(b"%PDF")
    assert fake.closed is True


def test_download_trop_gros(monkeypatch):
    fake = FakeResponse(b"%PDF-" + b"x" * 100)
    monkeypatch.setattr(cps_download.requests, "get", lambda *a, **k: fake)
    with pytest.raises(cps_download.DocumentTooLarge):
        cps_download.download_pdf("https://portail.ma/f.pdf", max_bytes=10)


def test_download_pas_un_pdf(monkeypatch):
    monkeypatch.setattr(cps_download.requests, "get",
                        lambda *a, **k: FakeResponse(b"<html>erreur</html>"))
    with pytest.raises(cps_download.NotAPdf):
        cps_download.download_pdf("https://portail.ma/f.pdf")


def test_fetch_detail_erreur_reseau(monkeypatch):
    def boom(*a, **k):
        raise requests.ConnectionError("indisponible")

    monkeypatch.setattr(cps_download.requests, "get", boom)
    with pytest.raises(cps_download.FetchError):
        cps_download.fetch_detail("https://portail.ma/avis/123")
