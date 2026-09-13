"""
Source Registry module for managing Tamil MP3 scrapers, domains,
capabilities, static configuration, runtime health, and failure isolation.
"""

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional

from scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class SourceHealth(str, Enum):
    """Runtime health status of a music source."""
    ENABLED_HEALTHY = "ENABLED_HEALTHY"
    ENABLED_DEGRADED = "ENABLED_DEGRADED"
    ENABLED_UNAVAILABLE = "ENABLED_UNAVAILABLE"
    DISABLED = "DISABLED"


@dataclass
class SourceCapabilities:
    """Capabilities supported by a music source."""
    supports_320kbps: bool = True
    supports_128kbps: bool = True
    requires_playwright: bool = False
    provides_direct_mp3: bool = True


@dataclass
class SourceConfig:
    """Static configuration for a music source."""
    name: str
    display_name: str
    domains: List[str]
    capabilities: SourceCapabilities = field(default_factory=SourceCapabilities)
    enabled: bool = True


@dataclass
class SourceRuntimeState:
    """Dynamic runtime health and reliability metrics for a source."""
    health_status: SourceHealth = SourceHealth.ENABLED_HEALTHY
    active_domain_index: int = 0
    last_successful_check: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_error: Optional[str] = None
    reliability_score: float = 1.0
    consecutive_successes: int = 0
    consecutive_failures: int = 0


class RegisteredSource:
    """Container pairing static configuration, scraper adapter, and runtime state."""

    def __init__(
        self,
        config: SourceConfig,
        scraper: Optional[BaseScraper] = None,
        runtime_state: Optional[SourceRuntimeState] = None,
    ):
        self.config = config
        self.scraper = scraper
        self.state = runtime_state or SourceRuntimeState()
        if not config.enabled:
            self.state.health_status = SourceHealth.DISABLED

        # Ensure scraper is set up with active domain
        if self.scraper and self.config.domains:
            domain_idx = self.state.active_domain_index % len(self.config.domains)
            self.scraper.base_url = self.config.domains[domain_idx]

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def display_name(self) -> str:
        return self.config.display_name

    @property
    def enabled(self) -> bool:
        return self.config.enabled

    @property
    def active_domain(self) -> str:
        """Get current active domain for the source."""
        if not self.config.domains:
            return ""
        idx = self.state.active_domain_index % len(self.config.domains)
        return self.config.domains[idx]

    @property
    def is_usable(self) -> bool:
        """True if the source is enabled and not completely unavailable or disabled."""
        if not self.config.enabled:
            return False
        return self.state.health_status in (
            SourceHealth.ENABLED_HEALTHY,
            SourceHealth.ENABLED_DEGRADED,
        )

    def record_success(self, timestamp: Optional[datetime] = None) -> None:
        """Record a successful operation or health check (supports recovery)."""
        now = timestamp or datetime.now()
        self.state.last_successful_check = now
        self.state.consecutive_successes += 1
        self.state.consecutive_failures = 0
        self.state.reliability_score = min(1.0, self.state.reliability_score + 0.05)

        # Recovery transition
        if self.config.enabled:
            if self.state.health_status in (SourceHealth.ENABLED_UNAVAILABLE, SourceHealth.ENABLED_DEGRADED):
                logger.info(f"Source '{self.name}' recovered: {self.state.health_status.value} -> ENABLED_HEALTHY (active domain: {self.active_domain})")
                self.state.health_status = SourceHealth.ENABLED_HEALTHY

    def record_failure(self, error_msg: str, timestamp: Optional[datetime] = None) -> None:
        """Record an operation or health check failure, performing domain failover if alternate domains exist."""
        now = timestamp or datetime.now()
        self.state.last_failure = now
        self.state.last_error = error_msg
        self.state.consecutive_failures += 1
        self.state.consecutive_successes = 0
        self.state.reliability_score = max(0.0, self.state.reliability_score - 0.15)

        num_domains = len(self.config.domains)
        if num_domains > 1:
            old_domain = self.active_domain
            self.state.active_domain_index = (self.state.active_domain_index + 1) % num_domains
            new_domain = self.active_domain
            if self.scraper:
                self.scraper.base_url = new_domain
            logger.warning(
                f"Source '{self.name}' domain failover: {old_domain} -> {new_domain} (failure: {error_msg})"
            )

        if self.config.enabled:
            # Mark unavailable after all domains fail at least once
            max_failures = max(3, num_domains)
            if self.state.consecutive_failures >= max_failures:
                self.state.health_status = SourceHealth.ENABLED_UNAVAILABLE
            else:
                self.state.health_status = SourceHealth.ENABLED_DEGRADED
            logger.warning(f"Source '{self.name}' failure #{self.state.consecutive_failures}: {error_msg}")


class SourceRegistry:
    """
    Central registry for all Tamil MP3 music sources.

    Provides thread-safe registration, status transitions, fallback domain
    selection, and isolated scraper retrieval.
    """

    def __init__(self):
        self._sources: Dict[str, RegisteredSource] = {}
        self._lock = threading.RLock()

    def register_source(
        self,
        config: SourceConfig,
        scraper: Optional[BaseScraper] = None,
        runtime_state: Optional[SourceRuntimeState] = None,
    ) -> RegisteredSource:
        """Register a new source configuration and adapter."""
        with self._lock:
            reg = RegisteredSource(config, scraper, runtime_state)
            self._sources[config.name] = reg
            logger.info(f"Registered source '{config.name}' (enabled={config.enabled}, status={reg.state.health_status.value})")
            return reg

    def get_source(self, name: str) -> Optional[RegisteredSource]:
        """Get registered source by name."""
        with self._lock:
            return self._sources.get(name)

    def get_all_sources(self) -> List[RegisteredSource]:
        """Get list of all registered sources."""
        with self._lock:
            return list(self._sources.values())

    def get_enabled_sources(self) -> List[RegisteredSource]:
        """Get list of enabled sources."""
        with self._lock:
            return [s for s in self._sources.values() if s.enabled]

    def get_usable_sources(self) -> List[RegisteredSource]:
        """Get list of usable sources (enabled & healthy/degraded)."""
        with self._lock:
            return [s for s in self._sources.values() if s.is_usable]

    def get_usable_scrapers(self) -> List[BaseScraper]:
        """Get active scraper instances for usable sources."""
        with self._lock:
            return [s.scraper for s in self.get_usable_sources() if s.scraper is not None]

    def record_success(self, name: str) -> None:
        """Record success for a named source."""
        with self._lock:
            src = self.get_source(name)
            if src:
                src.record_success()

    def record_failure(self, name: str, error_msg: str) -> None:
        """Record failure for a named source."""
        with self._lock:
            src = self.get_source(name)
            if src:
                src.record_failure(error_msg)

    def health_check_source(self, name: str) -> bool:
        """
        Execute connection check for a source and update its health status.

        Returns True if reachable, False otherwise. Does not crash if connection fails.
        """
        with self._lock:
            src = self.get_source(name)
            if not src or not src.enabled or not src.scraper:
                return False

            try:
                connected = src.scraper.test_connection()
                if connected:
                    src.record_success()
                    return True
                else:
                    src.record_failure("test_connection() returned False")
                    return False
            except Exception as e:
                src.record_failure(f"test_connection() exception: {e}")
                return False
