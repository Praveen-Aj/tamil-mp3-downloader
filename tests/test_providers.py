"""
Unit tests for Audio Providers and ProviderRegistry fallback.
"""

from pathlib import Path
from unittest.mock import MagicMock
import pytest

from library.providers.base import (
    AudioProvider, AudioCandidate, ResolvedStream, ProviderCapabilities, DownloadResult
)
from library.providers.registry import ProviderRegistry
from library.matching.matcher import TrackMatcher


class MockFailingProvider(AudioProvider):
    @property
    def name(self) -> str:
        return "mock_fail"

    @property
    def display_name(self) -> str:
        return "Mock Failing Provider"

    def is_available(self) -> bool:
        return True

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(name=self.name, display_name=self.display_name)

    def search(self, title, artist=None, duration_seconds=None, limit=5):
        return [AudioCandidate(provider_name=self.name, source_url="fail://url", title=title)]

    def resolve(self, candidate):
        return None

    def download(self, candidate, output_dir, filename_stem, progress_cb=None):
        return DownloadResult(success=False, error_message="Simulated connection failure", provider_name=self.name)


class MockWorkingProvider(AudioProvider):
    @property
    def name(self) -> str:
        return "mock_work"

    @property
    def display_name(self) -> str:
        return "Mock Working Provider"

    def is_available(self) -> bool:
        return True

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(name=self.name, display_name=self.display_name)

    def search(self, title, artist=None, duration_seconds=None, limit=5):
        return [AudioCandidate(provider_name=self.name, source_url="work://url", title=title)]

    def resolve(self, candidate):
        return ResolvedStream(stream_url="work://url", audio_format="mp3")

    def download(self, candidate, output_dir, filename_stem, progress_cb=None):
        out_file = output_dir / f"{filename_stem}.mp3"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(b"VALID_AUDIO_BYTES_TEST" * 50)
        return DownloadResult(success=True, file_path=out_file, size_bytes=len(b"VALID_AUDIO_BYTES_TEST" * 50), provider_name=self.name)


def test_provider_registry_init_and_query():
    reg = ProviderRegistry()
    providers = reg.get_all_providers()
    names = [p.name for p in providers]
    assert "youtube" in names
    assert "tamil_regional" in names
    assert "direct_http" in names


def test_provider_fallback_when_primary_fails(tmp_path):
    reg = ProviderRegistry(matcher=TrackMatcher())
    reg._providers.clear()
    reg._priority.clear()

    fail_p = MockFailingProvider()
    work_p = MockWorkingProvider()

    reg.register_provider(fail_p)
    reg.register_provider(work_p)

    cands = [
        AudioCandidate(provider_name="mock_fail", source_url="fail://test", title="Test Song"),
        AudioCandidate(provider_name="mock_work", source_url="work://test", title="Test Song"),
    ]

    res = reg.download_with_fallback(
        candidates=cands,
        output_dir=tmp_path,
        filename_stem="Test_Fallback",
    )

    assert res.success is True
    assert res.file_path.exists()
    assert res.provider_name == "mock_work"
