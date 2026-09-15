"""Opt-in live tests against external network providers. Run with `pytest -m live`."""

import pytest
from scrapers.masstamilan import MassTamilanScraper
from scrapers.tamilmp3 import Tamilmp3Scraper


@pytest.mark.live
def test_live_masstamilan_connection():
    """Verify live connectivity and non-empty response from MassTamilan."""
    s = MassTamilanScraper()
    connected = s.test_connection()
    assert connected is True, "MassTamilan live endpoint failed to connect"


@pytest.mark.live
def test_live_tamilmp3_connection():
    """Verify live connectivity and non-empty response from Tamilmp3."""
    s = Tamilmp3Scraper()
    connected = s.test_connection()
    assert connected is True, "Tamilmp3 live endpoint failed to connect"
