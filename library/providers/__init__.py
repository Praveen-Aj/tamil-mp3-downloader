"""
Pluggable Audio Providers package.
"""

from library.providers.base import (
    AudioProvider, AudioCandidate, ResolvedStream, ProviderCapabilities, DownloadResult
)
from library.providers.registry import ProviderRegistry
from library.providers.youtube_provider import YouTubeProvider
from library.providers.regional_provider import TamilRegionalProvider
from library.providers.direct_provider import DirectAudioProvider

__all__ = [
    "AudioProvider",
    "AudioCandidate",
    "ResolvedStream",
    "ProviderCapabilities",
    "DownloadResult",
    "ProviderRegistry",
    "YouTubeProvider",
    "TamilRegionalProvider",
    "DirectAudioProvider",
]
