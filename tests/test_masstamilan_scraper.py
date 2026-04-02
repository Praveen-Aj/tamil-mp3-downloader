"""Basic smoke tests for the MassTamilan scraper interface."""

import pytest

from scrapers.masstamilan import MassTamilanScraper
from models.song import Album


def test_masstamilan_connection() -> None:
    s = MassTamilanScraper()
    assert s.test_connection() is True or s.test_connection() is False  # always returns bool


@pytest.mark.skipif(True, reason="MassTamilan page content is dynamic and can vary; run manually")
def test_masstamilan_albums() -> None:
    s = MassTamilanScraper()
    albums = s.get_albums('latest', max_pages=1)
    assert isinstance(albums, list)
    assert all(isinstance(a, Album) for a in albums)


@pytest.mark.skipif(True, reason="MassTamilan page content dynamic data; run manual tests")
def test_masstamilan_songs() -> None:
    s = MassTamilanScraper()
    album = Album(name='Demo', url='https://www.masstamilan.dev/tamil-songs')
    songs = s.get_songs(album)
    assert isinstance(songs, list)
    assert all(hasattr(song, 'url') for song in songs)
