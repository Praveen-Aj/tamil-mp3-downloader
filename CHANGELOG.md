# Changelog

This changelog is generated from git history and repository state on branch `songs_downloader`.
Analyzed range: `723f080` to `238b510` (2026-04-02 to 2026-04-03).

## [Unreleased] - 2026-04-03

### Summary of New Features Added

#### 1) Cross-source search with fuzzy matching and download flow
- Added a `Search` path in the main CLI menu.
- Searches album/movie names across all configured sources.
- Uses fuzzy matching and shows numbered results for selection and download.
- Reuses existing scraper interfaces for result collection.

Files modified per feature:
- `main.py`
- `config/settings.py`

#### 2) Concurrent downloads with fallback
- Added concurrent download execution with `ThreadPoolExecutor`.
- Kept tqdm per-file and overall progress bars.
- Added automatic fallback to sequential mode if concurrent orchestration/workers fail.

Files modified per feature:
- `downloaders/http_downloader.py`
- `main.py`

#### 3) Resume support for partial downloads
- Added HTTP `Range` request support for partial `.part` files.
- Added skip for already completed files.
- Added resume indicator (`resumed`) in progress output.
- Added per-album download state file `.download_state.json`.

Files modified per feature:
- `downloaders/http_downloader.py`

#### 4) New scraper: FriendsTamilMP3
- Added `FriendsTamilMP3Scraper` implementing base scraper contract.
- Implemented category/album listing and song extraction.
- Integrated scraper into CLI source menu and search flow.
- Added source config entries and HTTP error handling.

Files modified per feature:
- `scrapers/friendstamilmp3.py`
- `scrapers/__init__.py`
- `main.py`
- `config/settings.py`
- `config/settings.json`

#### 5) ID3 metadata tagging after download
- Added metadata tagging using `mutagen` after successful MP3 download.
- Tags include artist, album, year, track number, and cover art (when available).
- Tagging is non-fatal (download success is preserved even if tagging fails).

Files modified per feature:
- `downloaders/http_downloader.py`
- `models/song.py`
- `main.py`
- `requirements.txt`

#### 6) Settings menu with persistent config
- Added CLI settings menu.
- Added settings to change output directory, toggle concurrency, set max workers, toggle progress bars.
- Persisted settings in `config/settings.json`.

Files modified per feature:
- `main.py`
- `config/settings.py`
- `config/settings.json`
- `downloaders/http_downloader.py`

#### 7) Maintainability and cleanup refactor
- Removed unused legacy utility modules.
- Expanded type hints across core modules and scrapers.
- Improved exception logging (`logger.exception`) in key flows.
- Kept current file structure and runtime behavior aligned with existing architecture.

Files modified per feature:
- `main.py`
- `config/settings.py`
- `utils/logger.py`
- `scrapers/isaimini.py`
- `scrapers/masstamilan.py`
- `scrapers/friendstamilmp3.py`
- `scripts/probe_masstamilan.py`
- `utils/downloader.py` (deleted)
- `utils/helper.py` (deleted)

## [3.0.0] - 2026-04-02

### Summary of New Features Added

#### Modular architecture rewrite and source expansion
- Reorganized project into modular packages (`scrapers`, `downloaders`, `models`, `config`, `utils`).
- Added base interfaces for scrapers and downloaders.
- Added MassTamilan scraper integration and supporting docs/scripts/tests.
- Archived classic implementation under `archive/`.

Files modified per feature:
- `main.py`
- `downloaders/base.py`
- `downloaders/http_downloader.py`
- `scrapers/base.py`
- `scrapers/isaimini.py`
- `scrapers/masstamilan.py`
- `models/song.py`
- `config/settings.py`
- `utils/logger.py`
- `tests/test_download_legacy.py`
- `tests/test_masstamilan_scraper.py`
- `docs/masstamilan_integration.md`
- `scripts/check_masstamilan.py`
- `scripts/check_masstamilan_playwright.py`
- `scripts/probe_masstamilan.py`
- `archive/main-classic.py` (moved)
- `archive/README-classic.md` (moved)

## Breaking Changes

- Potential API/import break for external scripts:
  - `utils/downloader.py` removed.
  - `utils/helper.py` removed.
- Classic app/assets moved under `archive/` during modular reorganization.
- For normal CLI usage, no intentional behavior-breaking changes were introduced.

## New Dependencies

- `mutagen>=1.47.0` (added for ID3 metadata tagging and cover art embedding)

## New CLI Options

### Main menu additions/changes
- `3. FriendsTamilMP3`
- `4. Search`
- `5. Settings`

### Settings menu
- `1. Change output directory`
- `2. Toggle concurrent downloads`
- `3. Set max workers`
- `4. Toggle progress bar`

## Migration Notes

1. Update/install dependencies:
- Run `pip install -r requirements.txt` to include `mutagen`.

2. Persisted settings:
- App settings now persist in `config/settings.json`.
- New keys to be aware of:
  - `download.concurrent_enabled`
  - `download.max_workers`
  - `ui.show_progress`

3. Download resume state:
- Per-album state is stored in `.download_state.json` under output album folders.
- Partial files use `.part`; completed files are skipped automatically on re-run.

4. If you imported removed legacy utils in custom scripts:
- Replace legacy imports with current modules:
  - `downloaders.http_downloader.HTTPDownloader`
  - `config.settings.settings`

5. ID3 tagging behavior:
- Tagging runs after successful MP3 download.
- If tagging fails or `mutagen` is unavailable, download still succeeds.
