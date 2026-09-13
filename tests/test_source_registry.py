"""Unit tests for SourceRegistry, SourceConfig, and SourceRuntimeState."""

import pytest
from datetime import datetime
from scrapers.base import BaseScraper
from scrapers.source_registry import (
    SourceRegistry,
    SourceConfig,
    SourceCapabilities,
    SourceHealth,
    SourceRuntimeState,
    RegisteredSource,
)


class DummyScraper(BaseScraper):
    def __init__(self, base_url: str = "https://example.com", is_healthy: bool = True):
        super().__init__(base_url)
        self.is_healthy = is_healthy

    def test_connection(self) -> bool:
        if not self.is_healthy:
            raise ConnectionError("Mock connection error")
        return True

    def get_albums(self, category: str = "latest", max_pages: int = 1, progress_cb=None):
        return []

    def get_songs(self, album):
        return []


def test_source_registration():
    reg = SourceRegistry()
    config = SourceConfig(
        name="masstamilan",
        display_name="MassTamilan",
        domains=["https://www.masstamilan.dev", "https://masstamilan.in"],
        capabilities=SourceCapabilities(supports_320kbps=True),
        enabled=True,
    )
    scraper = DummyScraper("https://www.masstamilan.dev")
    src = reg.register_source(config, scraper)

    assert src.name == "masstamilan"
    assert src.display_name == "MassTamilan"
    assert src.enabled is True
    assert src.is_usable is True
    assert reg.get_source("masstamilan") is src
    assert len(reg.get_all_sources()) == 1


def test_enabled_disabled_filtering():
    reg = SourceRegistry()
    cfg1 = SourceConfig(name="s1", display_name="S1", domains=["https://s1.com"], enabled=True)
    cfg2 = SourceConfig(name="s2", display_name="S2", domains=["https://s2.com"], enabled=False)

    reg.register_source(cfg1, DummyScraper("https://s1.com"))
    reg.register_source(cfg2, DummyScraper("https://s2.com"))

    enabled = reg.get_enabled_sources()
    usable = reg.get_usable_sources()

    assert len(enabled) == 1
    assert enabled[0].name == "s1"
    assert len(usable) == 1
    assert usable[0].name == "s1"


def test_health_transitions_and_failure_recording():
    reg = SourceRegistry()
    cfg = SourceConfig(name="s1", display_name="S1", domains=["https://s1.com"], enabled=True)
    src = reg.register_source(cfg, DummyScraper("https://s1.com"))

    assert src.state.health_status == SourceHealth.ENABLED_HEALTHY
    assert src.state.reliability_score == 1.0

    # Record 1 failure -> DEGRADED
    reg.record_failure("s1", "Timeout on page fetch")
    assert src.state.health_status == SourceHealth.ENABLED_DEGRADED
    assert src.state.consecutive_failures == 1
    assert src.state.reliability_score == 0.85

    # Record 2 failures total -> still DEGRADED
    reg.record_failure("s1", "Timeout on page fetch")
    assert src.state.health_status == SourceHealth.ENABLED_DEGRADED

    # Record 3 failures total -> ENABLED_UNAVAILABLE
    reg.record_failure("s1", "Server error 500")
    assert src.state.health_status == SourceHealth.ENABLED_UNAVAILABLE
    assert src.is_usable is False
    assert len(reg.get_usable_sources()) == 0


def test_health_recovery():
    reg = SourceRegistry()
    cfg = SourceConfig(name="s1", display_name="S1", domains=["https://s1.com"], enabled=True)
    src = reg.register_source(cfg, DummyScraper("https://s1.com"))

    # Force to unavailable state
    for _ in range(3):
        reg.record_failure("s1", "Error")
    assert src.state.health_status == SourceHealth.ENABLED_UNAVAILABLE

    # Successful check -> RECOVERY to ENABLED_HEALTHY!
    reg.record_success("s1")
    assert src.state.health_status == SourceHealth.ENABLED_HEALTHY
    assert src.state.consecutive_successes == 1
    assert src.state.consecutive_failures == 0
    assert src.is_usable is True


def test_reliability_scoring():
    reg = SourceRegistry()
    cfg = SourceConfig(name="s1", display_name="S1", domains=["https://s1.com"], enabled=True)
    src = reg.register_source(cfg, DummyScraper("https://s1.com"))

    initial_score = src.state.reliability_score
    reg.record_failure("s1", "Err")
    assert src.state.reliability_score == initial_score - 0.15

    reg.record_success("s1")
    assert src.state.reliability_score == (initial_score - 0.15) + 0.05


def test_source_isolation_health_checks():
    reg = SourceRegistry()
    h_cfg = SourceConfig(name="healthy", display_name="Healthy", domains=["https://h.com"], enabled=True)
    u_cfg = SourceConfig(name="unhealthy", display_name="Unhealthy", domains=["https://u.com"], enabled=True)

    h_src = reg.register_source(h_cfg, DummyScraper("https://h.com", is_healthy=True))
    u_src = reg.register_source(u_cfg, DummyScraper("https://u.com", is_healthy=False))

    res_h = reg.health_check_source("healthy")
    res_u = reg.health_check_source("unhealthy")

    assert res_h is True
    assert res_u is False
    assert h_src.state.health_status == SourceHealth.ENABLED_HEALTHY
    assert u_src.state.health_status == SourceHealth.ENABLED_DEGRADED
    assert len(reg.get_usable_sources()) == 2  # healthy + degraded are usable


def test_multiple_domains_fallback():
    cfg = SourceConfig(
        name="masstamilan",
        display_name="MassTamilan",
        domains=["https://www.masstamilan.dev", "https://masstamilan.in", "https://masstamilan.com"],
        enabled=True,
    )
    src = RegisteredSource(cfg)
    assert len(src.config.domains) == 3
    assert src.config.domains[0] == "https://www.masstamilan.dev"
