# Roadmap

Status snapshot date: 2026-04-04
Priority legend: `P0` = critical, `P1` = high, `P2` = medium.

## Completed Features

1. `P0` Modular architecture in place with clear layers: app orchestration, scrapers, downloader, models, settings, logging.
2. `P0` Multi-source scraping implemented for IsaiminiHQ, MassTamilan, and FriendsTamilMP3 via shared scraper interface.
3. `P0` Search flow implemented across all sources with fuzzy album matching and selectable numbered results.
4. `P0` Concurrent downloads implemented using `ThreadPoolExecutor` with tqdm and automatic sequential fallback on worker/orchestration failure.
5. `P0` Resume downloads implemented with HTTP Range handling, `.part` continuation, completed-file skip logic, and `.download_state.json` tracking.
6. `P0` Post-download ID3 tagging implemented with `mutagen` (artist, album, year, track, cover art when available).
7. `P0` Settings persistence implemented in `config/settings.json` for source, download, and UI preferences.
8. `P0` GUI-first runtime finalized (`gui.py`), with `main.py` reduced to compatibility launcher behavior.
9. `P0` Legacy test blocker removed from active test flow (`tests/test_download_legacy.py` removed).
10. `P1` Maintainability improvements delivered: unused legacy utils removed, broader type hints, improved exception logging paths.

## Partially Implemented Features

1. `P0` Non-blocking download UX is only partially met: downloads are concurrent, but navigation/control is still limited while active batches run.
2. `P1` MassTamilan automated tests are partly skipped and remain sensitive to upstream/network variability.
3. `P1` Source-aware output presentation is partial: some save-path messaging and naming still need consistency checks.
4. `P1` Site reliability handling is partial: upstream HTTP 500 pages are handled defensively but still reduce visible source coverage at runtime.
5. `P2` Search quality is functional but basic (`SequenceMatcher` heuristic); no advanced token/phonetic normalization.

## Missing Features

1. `P0` Stable automated test pipeline (unit tests + deterministic integration tests with mocks/fixtures) is missing.
2. `P0` CI workflow (lint/type/test gates on push/PR) is missing.
3. `P1` Background job queue for true non-blocking download control (enqueue/cancel/status while navigating UI) is missing.
4. `P1` Source health diagnostics command (quick scraper connectivity/selector checks) is missing from app UI tools.
5. `P2` Structured release process automation (version bump, changelog validation, packaging checks) is missing.

## Technical Debt

1. `P1` Output path logic still needs a full consistency pass so all source names are reflected in folder and status messaging.
2. `P1` Some older docs historically drifted from current GUI-first flow; this has been reduced but should be rechecked each release.
3. `P2` Scraper lifecycle contract is uneven (`_init_browser`/`_close_browser` no-ops for HTTP scraper), indicating interface leakage.

## Performance Improvements

1. `P1` Introduce a shared `requests.Session` strategy in downloader for connection reuse across file downloads.
2. `P1` Reduce extra network round-trips by making HEAD preflight optional for servers where GET metadata is sufficient.
3. `P1` Add adaptive worker tuning based on failure rate/latency (auto-scale down on repeated network/server throttling).
4. `P2` Add in-memory per-session cache for album pages during repeated search/category navigation.
5. `P2` Add lightweight retry classification (DNS/timeouts vs 4xx) to avoid unnecessary retries and shorten slow failure paths.

## Next Recommended Steps

1. `P0` Expand deterministic tests around downloader behavior and scraper parsing to make `pytest -q` broadly reliable.
2. `P0` Complete source-aware output path and status message consistency.
3. `P1` Implement a true background download queue so users can continue navigating menus while downloads run.
4. `P1` Continue UI polish in GUI/TUI (clearer status indicators and queue visibility).
5. `P1` Keep README/docs aligned with release behavior (sources, search, resume, tagging, settings, build steps).
6. `P1` Add a CI workflow with lint + tests + smoke checks to prevent regressions.
7. `P2` Improve search relevance with token normalization and optional configurable match thresholds.
