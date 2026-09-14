"""
Unit tests for UniversalUrlDetector and platform URL resolvers.
"""

import pytest
from library.url_resolver.detector import UniversalUrlDetector
from library.url_resolver.base import PlatformType, ContentType
from library.url_resolver.spotify import SpotifyResolver
from library.url_resolver.youtube import YouTubeResolver
from library.url_resolver.direct import DirectUrlResolver


@pytest.fixture
def detector():
    return UniversalUrlDetector()


def test_detect_spotify_urls(detector):
    track_url = "https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT"
    album_url = "https://open.spotify.com/album/1DFixLWuPkv3KT3TnV35m3"
    playlist_url = "https://open.spotify.com/playlist/37i9dQZF1DX4sWSpwq3LiO?si=abc"

    assert detector.detect_platform(track_url) == PlatformType.SPOTIFY
    assert detector.detect_platform(album_url) == PlatformType.SPOTIFY
    assert detector.detect_platform(playlist_url) == PlatformType.SPOTIFY


def test_detect_youtube_urls(detector):
    video_url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    short_url = "https://youtu.be/dQw4w9WgXcQ"
    playlist_url = "https://www.youtube.com/playlist?list=PLrEnWoR732-B4fZuq_wF39m3x9a9e-Mv"
    music_url = "https://music.youtube.com/watch?v=dQw4w9WgXcQ"

    assert detector.detect_platform(video_url) == PlatformType.YOUTUBE
    assert detector.detect_platform(short_url) == PlatformType.YOUTUBE
    assert detector.detect_platform(playlist_url) == PlatformType.YOUTUBE
    assert detector.detect_platform(music_url) == PlatformType.YOUTUBE


def test_detect_direct_and_regional_urls(detector):
    direct_mp3 = "https://example.com/audio/sample_track.mp3"
    direct_m4a = "https://example.com/stream/file.m4a"
    masstamilan_url = "https://www.masstamilan.dev/leo-songs"

    assert detector.detect_platform(direct_mp3) == PlatformType.DIRECT_AUDIO
    assert detector.detect_platform(direct_m4a) == PlatformType.DIRECT_AUDIO
    assert detector.detect_platform(masstamilan_url) == PlatformType.DIRECT_AUDIO  # Handled by DirectUrlResolver


def test_detect_unsupported_and_malformed_urls(detector):
    assert detector.detect_platform("not a url") == PlatformType.UNKNOWN
    assert detector.detect_platform("") == PlatformType.UNKNOWN
    assert detector.detect_platform("https://github.com/Praveen-Aj/repo") == PlatformType.UNKNOWN

    res_empty = detector.resolve("")
    assert not res_empty.is_valid
    assert "valid URL" in res_empty.error_message

    res_malformed = detector.resolve("ftp://server.com/song.mp3")
    assert not res_malformed.is_valid
    assert "http" in res_malformed.error_message


def test_direct_url_resolver_resolution():
    resolver = DirectUrlResolver()
    url = "https://cdn.example.com/music/Aalaporan-Tamizhan.mp3"
    res = resolver.resolve(url)

    assert res.platform == PlatformType.DIRECT_AUDIO
    assert res.content_type == ContentType.DIRECT_FILE
    assert len(res.tracks) == 1
    assert "Aalaporan Tamizhan" in res.tracks[0].title
