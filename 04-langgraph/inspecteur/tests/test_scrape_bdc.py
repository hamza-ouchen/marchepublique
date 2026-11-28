from bs4 import BeautifulSoup

import scrape_bdc


def test_collect_purchase_notices_keeps_open_unsaved_notices(monkeypatch):
    listing = """
    <article class="bdc-card">
      <span>Clôture</span><span>24 nov. 2099</span><span>à 15:00</span>
      <span>34-CRE-2099</span>
      <a href="/bdc/entreprise/consultation/show/412286">Manuels scolaires</a>
    </article>
    <article class="bdc-card">
      <span>Clôture</span><span>24 nov. 2099</span><span>à 15:00</span>
      <span>35-CRE-2099</span><span>Annulé</span>
      <a href="/bdc/entreprise/consultation/show/412287">Papeterie</a>
    </article>
    """
    detail = """
    <span class="fw-bold">Date mise en ligne</span><span>23/11/2099 14:25</span>
    <span class="font-bold">Acheteur public</span><span>Commune</span>
    <span class="font-bold">Lieu d'exécution</span><span>MAROC, CASABLANCA</span>
    <span class="font-bold">Catégorie principale</span><span>Fournitures</span>
    """
    imported = []
    monkeypatch.setattr(scrape_bdc.db_cps, "query", lambda *_: [])
    monkeypatch.setattr(scrape_bdc, "_read", lambda url: BeautifulSoup(
        listing if url == scrape_bdc.LISTING else detail, "html.parser",
    ))
    monkeypatch.setattr(scrape_bdc.scrape_portal, "import_to_db",
                        lambda rows, _: imported.extend(rows) or len(rows))

    assert scrape_bdc.collect_purchase_notices("2099-11-23", 1)["imported"] == 1
    assert imported[0]["source_ref"] == "34-CRE-2099 [bdc:412286]"
    assert imported[0]["date_publication"] == "2099-11-23"
    assert imported[0]["deadline"] == "2099-11-24"
    assert imported[0]["offer_type"] == "bon_de_commande"
