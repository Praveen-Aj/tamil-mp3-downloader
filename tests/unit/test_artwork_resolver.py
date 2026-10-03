"""
Unit tests for ArtworkResolver and Multi-tier Artwork Pipeline.
"""

from unittest.mock import MagicMock
from PIL import Image

from library.artwork import ArtworkManager, ArtworkState, ResolutionResult


def test_artwork_resolver_fallback_movie(tmp_path):
    """Test that resolving a movie without a poster returns a procedural fallback."""
    cache_dir = tmp_path / "art_cache"
    manager = ArtworkManager(cache_dir=cache_dir)
    resolver = manager.resolver

    mock_service = MagicMock()
    mock_service.db.get_movie.return_value = None

    result = resolver.resolve(
        category="movie",
        entity_id="9999",
        service=mock_service,
        size=(150, 150),
        allow_async_enrich=False,
    )

    assert isinstance(result, ResolutionResult)
    assert result.state in (ArtworkState.NOT_FOUND, ArtworkState.PENDING)
    assert result.source_type == "procedural_fallback"
    assert isinstance(result.image, Image.Image)
    assert result.image.size == (150, 150)


def test_artwork_resolver_movie_with_poster(tmp_path):
    """Test resolving a movie with an existing poster URL."""
    cache_dir = tmp_path / "art_cache"
    manager = ArtworkManager(cache_dir=cache_dir)
    resolver = manager.resolver

    mock_movie = MagicMock()
    mock_movie.id = 101
    mock_movie.title = "Roja"
    mock_movie.poster_url = "https://example.com/roja.jpg"

    mock_service = MagicMock()
    mock_service.db.get_movie.return_value = mock_movie

    test_img = Image.new("RGB", (200, 200), color=(100, 150, 200))
    resolver._fetch_remote_url = MagicMock(return_value=test_img)

    result = resolver.resolve(
        category="movie",
        entity_id="101",
        service=mock_service,
        size=(200, 200),
        allow_async_enrich=False,
    )

    assert result.state == ArtworkState.FOUND
    assert result.source_type == "remote_verified"
    assert result.confidence >= 0.8
    assert result.image.size == (200, 200)


def test_artwork_resolver_caching(tmp_path):
    """Test that resolving the same entity twice hits the in-memory cache."""
    cache_dir = tmp_path / "art_cache"
    manager = ArtworkManager(cache_dir=cache_dir)
    resolver = manager.resolver

    mock_movie = MagicMock()
    mock_movie.id = 202
    mock_movie.title = "Baashha"
    mock_movie.poster_url = "https://example.com/baashha.jpg"

    mock_service = MagicMock()
    mock_service.db.get_movie.return_value = mock_movie

    test_img = Image.new("RGB", (100, 100), color=(50, 50, 50))
    resolver._fetch_remote_url = MagicMock(return_value=test_img)

    # First call
    res1 = resolver.resolve("movie", "202", mock_service, size=(100, 100))
    # Second call
    res2 = resolver.resolve("movie", "202", mock_service, size=(100, 100))

    assert res1.image == res2.image
    assert res2.state == ArtworkState.FOUND
    assert res2.source_type == "memory_cache"
    # _fetch_remote_url should only be called once
    assert resolver._fetch_remote_url.call_count == 1
