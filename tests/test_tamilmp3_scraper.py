"""Unit & integration tests for Tamilmp3Scraper (Tamilmp3.in / Kuttyweb)."""

import pytest
from unittest.mock import MagicMock, patch

from models.song import Album, Song
from scrapers.tamilmp3 import Tamilmp3Scraper


_SAMPLE_INDEX_HTML = """
<!DOCTYPE html>
<html>
<head><title>Tamil Mp3 Songs Free Download | Tamilmp3.in</title></head>
<body>
  <h1>Tamil Mp3 Songs</h1>
  <div class="album-item">
    <a href="/anbil-avan-songs">Anbil Avan (2026)</a>
  </div>
  <div class="album-item">
    <a href="/see-u-songs">See U (2026)</a>
  </div>
</body>
</html>
"""

_SAMPLE_ALBUM_HTML = """
<!DOCTYPE html>
<html>
<head><title>Anbil Avan Tamil Mp3 Songs Download | Tamilmp3.in</title></head>
<body>
  <div class="album-info">
    <h1>Anbil Avan</h1>
    <p>Music: Govind Vasantha</p>
    <p>Director: R.Kaarthikeyan</p>
  </div>
  <div class="song-card">
    <h3>Kalla Nikkiriye</h3>
    <a class="btn-dl" data-path="Tamil Mp3 Songs/2026/Anbil Avan/Anbil Avan 320kbps/Kalla Nikkiriye.mp3">320kbps (9.3 MB)</a>
    <a class="btn-dl" data-path="Tamil Mp3 Songs/2026/Anbil Avan/Anbil Avan 128kbps/Kalla Nikkiriye.mp3">128kbps (3.9 MB)</a>
  </div>
  <div class="song-card">
    <h3>Title Theme</h3>
    <a class="btn-dl" data-path="Tamil Mp3 Songs/2026/Anbil Avan/Anbil Avan 320kbps/Anbil Avan - Title Theme.mp3">320kbps (3.0 MB)</a>
    <a class="btn-dl" data-path="Tamil Mp3 Songs/2026/Anbil Avan/Anbil Avan 128kbps/Anbil Avan - Title Theme.mp3">128kbps (1.8 MB)</a>
  </div>
</body>
</html>
"""

_SAMPLE_TOKEN_JSON = {
    "url": "https://dl.tamilmp3.xyz/download.php?path=Tamil+Mp3+Songs%2F2026%2FAnbil+Avan%2FAnbil+Avan+320kbps%2FKalla+Nikkiriye.mp3&serve=1&token=mock123"
}


def test_tamilmp3_scraper_initialization():
    scraper = Tamilmp3Scraper("https://tamilmp3.in")
    assert scraper.base_url == "https://tamilmp3.in"
    assert scraper.get_source_name() == "tamilmp3"


@patch("requests.Session.get")
def test_tamilmp3_test_connection_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = "Welcome to Tamilmp3.in Free MP3 Download Kuttyweb"
    mock_get.return_value = mock_resp

    scraper = Tamilmp3Scraper()
    assert scraper.test_connection() is True


@patch("requests.Session.get")
def test_tamilmp3_get_albums_parser(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = _SAMPLE_INDEX_HTML
    mock_get.return_value = mock_resp

    scraper = Tamilmp3Scraper()
    albums = scraper.get_albums(category="latest", max_pages=1)

    assert len(albums) == 2
    assert albums[0].name == "Anbil Avan (2026)"
    assert albums[0].url == "https://tamilmp3.in/anbil-avan-songs"
    assert albums[0].year == 2026


@patch("requests.Session.get")
def test_tamilmp3_get_songs_parser(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = _SAMPLE_ALBUM_HTML
    mock_get.return_value = mock_resp

    scraper = Tamilmp3Scraper()
    album = Album(name="Anbil Avan", url="https://tamilmp3.in/anbil-avan-songs", year=2026)
    songs = scraper.get_songs(album)

    assert len(songs) == 2
    track1 = next(s for s in songs if "Kalla Nikkiriye" in s.name)
    assert track1.artist == "Govind Vasantha"
    assert track1.quality == "320kbps"
    assert track1.size_mb == 9.3
    assert hasattr(track1, "download_urls")
    assert "320" in track1.download_urls
    assert "128" in track1.download_urls


@patch("requests.Session.head")
@patch("requests.Session.post")
def test_tamilmp3_get_download_url_dynamic_token(mock_post, mock_head):
    # Mock token.php POST response
    mock_token_resp = MagicMock()
    mock_token_resp.status_code = 200
    mock_token_resp.text = '{"url": "https://dl.tamilmp3.xyz/download.php?path=mock.mp3"}'
    mock_token_resp.json.return_value = {"url": "https://dl.tamilmp3.xyz/download.php?path=mock.mp3"}
    mock_post.return_value = mock_token_resp

    # Mock audio URL HEAD response
    mock_head_resp = MagicMock()
    mock_head_resp.status_code = 200
    mock_head_resp.headers = {"Content-Type": "audio/mpeg", "Content-Length": "9700799"}
    mock_head.return_value = mock_head_resp

    scraper = Tamilmp3Scraper()
    song = Song(
        name="Kalla Nikkiriye",
        url="https://tamilmp3.in/anbil-avan-songs",
        quality="320kbps",
    )
    song.download_urls = {
        "320": "Tamil Mp3 Songs/2026/Anbil Avan/Anbil Avan 320kbps/Kalla Nikkiriye.mp3",
        "128": "Tamil Mp3 Songs/2026/Anbil Avan/Anbil Avan 128kbps/Kalla Nikkiriye.mp3",
    }

    dl_url = scraper.get_download_url(song, quality="320")

    assert dl_url == "https://dl.tamilmp3.xyz/download.php?path=mock.mp3"
    mock_post.assert_called_once()
    mock_head.assert_called_once()


@pytest.mark.live
def test_live_tamilmp3_connection():
    """Optional live integration test."""
    scraper = Tamilmp3Scraper()
    connected = scraper.test_connection()
    assert connected is True
