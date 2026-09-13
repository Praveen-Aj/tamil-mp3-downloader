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
        download_reference="Tamil Mp3 Songs/2026/Anbil Avan/Anbil Avan 320kbps/Kalla Nikkiriye.mp3",
    )

    dl_url = scraper.get_download_url(song, quality="320")

    assert dl_url == "https://dl.tamilmp3.xyz/download.php?path=mock.mp3"
    mock_post.assert_called_once()
    mock_head.assert_called_once()


@patch("requests.Session.get")
@patch("requests.Session.head")
def test_verify_audio_url_honest_strategy(mock_head, mock_get):
    scraper = Tamilmp3Scraper()

    # Case 1: HEAD returns status 200 with audio/mpeg Content-Type -> Verified True
    h1 = MagicMock()
    h1.status_code = 200
    h1.headers = {"Content-Type": "audio/mpeg"}
    mock_head.return_value = h1

    assert scraper._verify_audio_url("https://example.com/song.mp3") is True

    # Case 2: HEAD fails (405/500/blocked) but Range GET succeeds with ID3 magic bytes -> Verified True
    mock_head.side_effect = Exception("HEAD blocked by CDN")
    
    g1 = MagicMock()
    g1.status_code = 206
    g1.headers = {"Content-Type": "application/octet-stream"}
    g1.raw.read.return_value = b"ID3\x04\x00\x00\x00"
    g1.__enter__.return_value = g1
    mock_get.return_value = g1

    assert scraper._verify_audio_url("https://example.com/song.mp3") is True

    # Case 3: HEAD fails and Range GET returns 404 HTML page -> Verified FALSE (never pretends passed)
    g2 = MagicMock()
    g2.status_code = 404
    g2.headers = {"Content-Type": "text/html"}
    g2.raw.read.return_value = b"<html>404 Not Found</html>"
    g2.__enter__.return_value = g2
    mock_get.return_value = g2

    assert scraper._verify_audio_url("https://example.com/invalid.mp3") is False


@pytest.mark.live
def test_live_tamilmp3_connection():
    """Optional live connection check."""
    scraper = Tamilmp3Scraper()
    connected = scraper.test_connection()
    assert connected is True


@pytest.mark.live
def test_live_tamilmp3_full_protocol():
    """
    Live integration test verifying:
    Tamilmp3 page -> actual data-path -> actual token.php request -> fresh signed URL -> bounded Range request audio validation.
    """
    scraper = Tamilmp3Scraper()
    assert scraper.test_connection() is True

    # 1. Get real albums
    albums = scraper.get_albums(category="latest", max_pages=1)
    assert len(albums) > 0, "No albums found on live Tamilmp3"
    target_album = albums[0]

    # 2. Get real songs
    songs = scraper.get_songs(target_album)
    assert len(songs) > 0, f"No songs found for album {target_album.url}"
    target_song = songs[0]

    # Check stable download_reference
    assert getattr(target_song, "download_reference", None), "Missing download_reference on discovered Song"

    # 3. Generate signed URL via token.php
    signed_url = scraper.get_download_url(target_song)
    assert signed_url is not None, "get_download_url failed to return signed URL"
    assert "http" in signed_url

    # 4. Verify audio stream using Range GET / HEAD validation
    verified = scraper._verify_audio_url(signed_url)
    assert verified is True, f"Audio verification failed for live signed URL: {signed_url}"

