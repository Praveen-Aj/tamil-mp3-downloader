"""Scraper package with source-specific site integrations."""

from scrapers.friendstamilmp3 import FriendsTamilMP3Scraper
from scrapers.isaimini import IsaiminiScraper
from scrapers.masstamilan import MassTamilanScraper

__all__ = [
    "IsaiminiScraper",
    "MassTamilanScraper",
    "FriendsTamilMP3Scraper",
]
