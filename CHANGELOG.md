# Changelog

This changelog is generated from git history and repository state on branch `songs_downloader`.
Analyzed range: `723f080` to `238b510` (2026-04-02 to 2026-04-03).

## [4.1.0] - 2026-09-14

### Universal URL / Playlist Acquisition & Modern UI Overhaul

This release elevates the application into a universal music acquisition platform with pluggable audio stream resolution and persistent playlist state.

### Added
- **Universal URL Import Engine**: Instant platform detection and metadata parsing for Spotify (tracks, albums, playlists), YouTube, YouTube Music, Tamil regional sources, and direct audio files.
- **Pluggable Audio Provider Architecture**: Abstract `AudioProvider` interface decoupling metadata extraction from stream resolution, with core implementations for `YouTubeProvider` (powered by `yt-dlp`), `TamilRegionalProvider`, and `DirectAudioProvider`.
- **Multi-Factor Track Matching (`TrackMatcher`)**: Fuzzy matching combining normalized sequence matching, token set overlap, and duration delta scoring with tiered classifications (`HIGH`, `MEDIUM`, `LOW`, `NO_MATCH`).
- **Persistent Resumable Playlist Jobs**: SQLite-backed `import_jobs` and `import_job_items` allowing multi-track playlist downloads to resume safely across application restarts.
- **Complete Visual & UX Redesign**:
  - Centralized design system (`ui/theme.py`) featuring rich obsidian/navy dark palette, semantic status colors, and consistent typography tokens.
  - Redesigned sidebar with categorized navigation (LIBRARY, DOWNLOADS, SYSTEM) and live notification badge pills.
  - Centerpiece Add Music experience featuring large import field, platform chips, and full Playlist Result UI with individual checkboxes, bulk filters, search, and prominent Download Selected CTA.
  - Real Download Manager queue with aggregate progress, speed, ETA, and individual track cards with inline actions (Pause, Resume, Retry, Open Folder).
  - Review Results center featuring conflict cards with reason pills, candidate comparisons, and inspector actions.
  - Consumer-friendly Source Health status dashboard with response times and expandable diagnostics.
  - Tabbed/grouped Settings center and interactive Help & User Guide center.
- **Automatic ID3 Tagging & Artwork Injection**: Mutagen integration writing ID3v2.3 tags and embedding cover artwork into completed audio files.

### Changed
- Local MP3 folder importing repositioned under `Library → Import Existing Files` as a secondary capability.
- Added `yt-dlp>=2024.0.0` dependency with graceful fallback when FFmpeg is not detected.
- Database schema bumped to Version 3 via `DatabaseMigrator`.

## [4.0.0] - 2026-09-14

### Major Architectural Rewrite: Library-Centric V4

This release fundamentally changes the application from a "search-and-download" scraper tool into a robust **Music Library Manager** framework. 

### Added
- **Canonical SQLite Library**: Discovered songs are deduplicated, securely stored locally, and tracked across sessions.
- **Source Health Registry**: Dynamic circuit-breaker tracking of scraper health. Sites experiencing HTTP errors automatically fallback to alternate domains.
- **Download Planner Engine**: Automatically computes quality upgrades (e.g., 128kbps -> 320kbps) and skips songs the user already owns.
- **CustomTkinter UI Module**: Complete modular UI rewrite featuring Dashboard, Canonical Library View, Discovery Planner, and Source Health visualizers.
- **Thread-Safe Download Registry**: `threading.RLock`-backed registry guaranteeing concurrency safety and protecting against duplicate downloads of the same file.
- **Local MP3 Importer**: Ability to scan existing MP3 collections and transparently map them to the canonical database.
- **Database Migrations**: Idempotent SQL migration engine protecting library schema evolution.

### Changed
- `main.py` is now the primary CustomTkinter entrypoint instead of `gui.py`.
- Legacy `gui.py` and `tui.py` moved to `docs/archive`.
- Downloads are now asynchronous by default via `LibraryService`.

## [3.x] - Legacy Versions

### Summary of Latest Status Updates

#### 1) GUI-first runtime and packaging finalization
- Set GUI app flow as the primary runtime path for this release line.
- Kept `main.py` as a thin compatibility launcher to avoid old entrypoint breakage.
- Updated PyInstaller flow to package the GUI entrypoint in windowed mode.

Files modified per feature:
- `gui.py`
- `main.py`
- `scripts/tamil_mp3_downloader.spec`

#### 2) Runtime stability adjustments
- Avoided caching empty song payloads in GUI fetch flow.
- Ignored previously cached empty song entries to reduce false "no songs" outcomes.
- Simplified GUI layout by removing extra preview/duplicate queue panel usage.

Files modified per feature:
- `gui.py`

#### 3) Test and legacy conflict cleanup
- Removed obsolete legacy test causing collection/import issues.
- Kept active scraper test path as the current validated automated check.

Files modified per feature:
- `tests/test_download_legacy.py` (deleted)
- `tests/test_masstamilan_scraper.py`

#### 4) Documentation refresh
- Updated status and usage docs to match current GUI-first behavior.
- Updated architecture and roadmap notes to remove stale legacy blockers.

Files modified per feature:
- `README.md`
- `ROADMAP.md`
- `ARCHITECTURE.md`
- `docs/CONTRIBUTING.md`
- `docs/masstamilan_integration.md`
- `docs/DOWNLOAD.md`

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
