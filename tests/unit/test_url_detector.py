"""Unit tests for UniversalUrlDetector and platform categorization."""

import pytest
from library.url_resolver.detector import UniversalUrlDetector
from library.url_resolver.base import PlatformType, ContentType


@pytest.fixture
def detector():
    return UniversalUrlDetector()


@pytest.mark.unit
def test_detect_spotify_urls(detector):
    assert detector.detect_platform("https://open.spotify.com/track/4cOdK2wGLETKBW3PvgPWqT") == PlatformType.SPOTIFY
    assert detector.detect_platform("https://open.spotify.com/playlist/37i9dQZF1DX4WYpdgoIcn6") == PlatformType.SPOTIFY
    assert detector.detect_platform("https://open.spotify.com/album/4m2880jivSbbyEGAKfITCa") == PlatformType.SPOTIFY


@pytest.mark.unit
def test_detect_youtube_urls(detector):
    assert detector.detect_platform("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == PlatformType.YOUTUBE
    assert detector.detect_platform("https://youtu.be/dQw4w9WgXcQ") == PlatformType.YOUTUBE
    assert detector.detect_platform("https://www.youtube.com/playlist?list=PLrAl5Gfy38yB9aV-GZgQvLh0z_V4N8I1m") == PlatformType.YOUTUBE


@pytest.mark.unit
def test_detect_direct_and_regional_urls(detector):
    assert detector.detect_platform("https://audio.example.com/stream/file.mp3") == PlatformType.DIRECT_AUDIO
    assert detector.detect_platform("https://masstamilan.dev/tamil-songs/beast") == PlatformType.DIRECT_AUDIO


@pytest.mark.unit
def test_detect_unknown_urls(detector):
    assert detector.detect_platform("https://unsupported.example.com/index.html") == PlatformType.UNKNOWN
    assert detector.detect_platform("") == PlatformType.UNKNOWN
