# Roadmap

Status snapshot date: 2026-04-03
Priority legend: `P0` = critical, `P1` = high, `P2` = medium.

## Completed Features

1. `P0` Modular architecture in place with clear layers: CLI orchestration, scrapers, downloader, models, settings, logging.
2. `P0` Multi-source scraping implemented for IsaiminiHQ, MassTamilan, and FriendsTamilMP3 via shared scraper interface.
3. `P0` Search flow implemented across all sources with fuzzy album matching and selectable numbered results.
4. `P0` Concurrent downloads implemented using `ThreadPoolExecutor` with tqdm and automatic sequential fallback on worker/orchestration failure.
5. `P0` Resume downloads implemented with HTTP Range handling, `.part` continuation, completed-file skip logic, and `.download_state.json` tracking.
6. `P0` Post-download ID3 tagging implemented with `mutagen` (artist, album, year, track, cover art when available).
7. `P0` Settings menu implemented with persistence in `config/settings.json` (output directory, concurrent toggle, max workers, progress bar toggle).
8. `P1` Maintainability improvements delivered: unused legacy utils removed, broader type hints, improved exception logging paths.

## Partially Implemented Features

1. `P0` Non-blocking UI download requirement is only partially met: downloads are concurrent, but main CLI interaction remains blocked until the batch completes.
2. `P0` Test coverage exists but is partially usable: `pytest` collection currently fails due legacy import paths in `tests/test_download_legacy.py` and environment/package-path assumptions.
3. `P1` MassTamilan automated tests are mostly skipped and rely on manual/network variability; regression confidence remains limited.
4. `P1` Source-aware output presentation is partial: save path messaging and directory naming currently use `IsaiminiHQ` for all sources.
5. `P2` Search quality is functional but basic (`SequenceMatcher` heuristic); no advanced token/phonetic normalization.

## Missing Features

1. `P0` Stable automated test pipeline (unit tests + deterministic integration tests with mocks/fixtures) is missing.
2. `P0` CI workflow (lint/type/test gates on push/PR) is missing.
3. `P1` Background job queue for true non-blocking download control (enqueue/cancel/status while navigating UI) is missing.
4. `P1` Source health diagnostics command (quick scraper connectivity/selector checks) is missing from the CLI.
5. `P2` Structured release process automation (version bump, changelog validation, packaging checks) is missing.

## Technical Debt

1. `P0` `tests/test_download_legacy.py` is a legacy script-style test with outdated imports and blocks test collection.
2. `P1` `main.py` is large and handles many concerns (menu UI, search orchestration, album workflow, settings), increasing change risk.
3. `P1` Output path logic is hardcoded to `IsaiminiHQ` in downloader/user messaging instead of using source context.
4. `P1` Documentation drift: README content is stale versus current features and contains duplicated/encoding-noise sections.
5. `P2` Scraper lifecycle contract is uneven (`_init_browser`/`_close_browser` no-ops for HTTP scraper), indicating interface leakage.

## Performance Improvements

1. `P1` Introduce a shared `requests.Session` strategy in downloader for connection reuse across file downloads.
2. `P1` Reduce extra network round-trips by making HEAD preflight optional for servers where GET metadata is sufficient.
3. `P1` Add adaptive worker tuning based on failure rate/latency (auto-scale down on repeated network/server throttling).
4. `P2` Add in-memory per-session cache for album pages during repeated search/category navigation.
5. `P2` Add lightweight retry classification (DNS/timeouts vs 4xx) to avoid unnecessary retries and shorten slow failure paths.

## Next Recommended Steps

1. `P0` Repair test health first: replace legacy import paths, convert script-style test to proper pytest cases, and make `pytest -q` green.
2. `P0` Fix source-aware output paths and status messaging so each source writes/reports under its own directory namespace.
3. `P1` Implement a true background download queue so users can continue navigating menus while downloads run.
4. `P1` Split `main.py` orchestration into smaller modules (menu controller, search service, download workflow, settings UI).
5. `P1` Refresh README/docs to match actual v3 behavior (sources, search, resume, tagging, settings, current menu).
6. `P1` Add a CI workflow with lint + tests + smoke checks to prevent regressions.
7. `P2` Improve search relevance with token normalization and optional configurable match thresholds.
