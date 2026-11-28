import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import scrape_portal  # noqa: E402


def test_canonical_url_normalizes_tracking_and_fragment():
    brut = "HTTPS://WWW.Marchespublics.gov.ma//index.php?utm_source=x&b=2&fbclid=1#frag"
    assert scrape_portal.canonical_url(brut) == (
        "https://marchespublics.gov.ma/index.php?b=2"
    )


def test_tender_identity_dedupes_same_canonical_url():
    commun = {
        "source_ref": "portal:A",
        "url": "https://marchespublics.gov.ma/index.php?b=2&utm_source=mail",
    }
    autre = {
        "source_ref": "portal:B",
        "url": "https://www.marchespublics.gov.ma//index.php?b=2#details",
    }
    identite_a = scrape_portal._tender_identity(commun)
    identite_b = scrape_portal._tender_identity(autre)
    assert identite_a[2] == identite_b[2]
    assert identite_a[3] == identite_b[3]
