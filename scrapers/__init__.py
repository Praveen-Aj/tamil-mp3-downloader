"""Scraper package with source-specific site integrations."""

from scrapers.base import BaseScraper
from scrapers.friendstamilmp3 import FriendsTamilMP3Scraper
from scrapers.isaimini import IsaiminiScraper
from scrapers.kollysongs import KollySongsScraper
from scrapers.masstamilan import MassTamilanScraper
from scrapers.tamilmp3 import Tamilmp3Scraper
from scrapers.source_registry import (
    SourceRegistry,
    SourceConfig,
    SourceCapabilities,
    SourceHealth,
    SourceRuntimeState,
    RegisteredSource,
)

__all__ = [
    "BaseScraper",
    "IsaiminiScraper",
    "MassTamilanScraper",
    "FriendsTamilMP3Scraper",
    "KollySongsScraper",
    "Tamilmp3Scraper",
    "SourceRegistry",
    "SourceConfig",
    "SourceCapabilities",
    "SourceHealth",
    "SourceRuntimeState",
    "RegisteredSource",
]
