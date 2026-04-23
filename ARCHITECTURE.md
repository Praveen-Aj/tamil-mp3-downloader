# Architecture

This document describes the current architecture of the Tamil MP3 Downloader codebase.

## Current Folder Structure

```text
tamil-mp3-downloader/
|-- gui.py
|-- tui.py
|-- main.py
|-- requirements.txt
|-- VERSION
|-- README.md
|-- CHANGELOG.md
|-- config/
|   |-- __init__.py
|   |-- settings.py
|   `-- settings.json
|-- models/
|   |-- __init__.py
|   `-- song.py
|-- scrapers/
|   |-- __init__.py
|   |-- base.py
|   |-- isaimini.py
|   |-- masstamilan.py
|   `-- friendstamilmp3.py
|-- downloaders/
|   |-- __init__.py
|   |-- base.py
|   `-- http_downloader.py
|-- utils/
|   `-- logger.py
|-- scripts/
|   |-- build_exe.bat
|   |-- run_all.sh
|   |-- check_masstamilan.py
|   |-- check_masstamilan_playwright.py
|   |-- probe_masstamilan.py
|   `-- tamil_mp3_downloader.spec
|-- tests/
|   `-- test_masstamilan_scraper.py
|-- docs/
|   `-- masstamilan_integration.md
|-- archive/
|   |-- main-classic.py
|   |-- README-classic.md
|   `-- data/
|-- output/
`-- logs/
```

## High-Level Module Architecture

```mermaid
flowchart TB
  A["gui.py / tui.py (App Orchestrators)"] --> B["config/settings.py (persistent settings)"]
    A --> C["scrapers/* (source adapters)"]
    A --> D["downloaders/http_downloader.py"]
    A --> E["models/song.py (Album, Song, DownloadResult)"]
    A --> F["utils/logger.py"]

  G["main.py (compatibility shim)"] --> A

    C --> E
    D --> E
    D --> B
```

## Scraper Architecture

### Contract
- `scrapers/base.py` defines `BaseScraper` with:
  - `get_albums(category, max_pages)`
  - `get_songs(album)`
  - `test_connection()`

### Implementations
- `IsaiminiScraper`
  - Playwright-based scraping.
  - Uses injected JS helpers to extract album/song data from rendered pages.
  - Supports paging and category URLs (`latest`, `2026`, `2025`, `old`).
- `MassTamilanScraper`
  - Primary fetch via `cloudscraper`.
  - Fallback render via Playwright when needed.
  - Parses album/song links using BeautifulSoup selectors.
- `FriendsTamilMP3Scraper`
  - Requests + BeautifulSoup scraper.
  - Uses query-based category pages and song extraction from direct audio links.
  - Keeps no-op `_init_browser` and `_close_browser` hooks for shared scraper compatibility.

```mermaid
classDiagram
    class BaseScraper {
      +get_albums(category, max_pages) List~Album~
      +get_songs(album) List~Song~
      +test_connection() bool
    }

    class IsaiminiScraper
    class MassTamilanScraper
    class FriendsTamilMP3Scraper

    BaseScraper <|-- IsaiminiScraper
    BaseScraper <|-- MassTamilanScraper
    BaseScraper <|-- FriendsTamilMP3Scraper
```

## Downloader Pipeline

`HTTPDownloader` is the concrete downloader and central download pipeline.

### Pipeline stages
1. GUI/TUI prepares `Song` objects (album context + tag fields).
2. Downloader chooses mode:
   - concurrent: `download_concurrent(...)`
   - sequential: `download_songs(...)`
3. For each song:
   - prefer best URL (`_best_url`, favors 320 kbps)
   - attempt download with retries (`_download_with_progress`)
   - resolve final URL via HEAD
   - compute output path + `.part` path + state path
   - resume/skip logic
   - stream response to disk
   - rename `.part` to final file
   - apply ID3 tags (non-fatal)
   - persist state entry and return `DownloadResult`

```mermaid
flowchart TD
    A["Song input"] --> B["_best_url (prefer 320)"]
    B --> C["_download_with_progress (retry loop)"]
    C --> D["_attempt_download"]
    D --> E["HEAD resolve final URL"]
    E --> F["Path planning (.part + .download_state.json)"]
    F --> G{"File already complete?"}
    G -- "yes" --> H["Skip + mark completed"]
    G -- "no" --> I["GET stream (Range if partial)"]
    I --> J["Write chunks to .part"]
    J --> K["Rename to final file"]
    K --> L["Apply ID3 tags (mutagen)"]
    L --> M["Update state completed=true"]
```

## App Flow

The app flow dispatches to source/category browsing, search, and settings in GUI/TUI entrypoints.

```mermaid
flowchart TD
  A["Start app"] --> B["Source/category selection"]
  B --> C["Album list"]
  C --> D["Song fetch"]
  D --> E["Queue + download"]
  B --> F["Search"]
  F --> C
  B --> G["Settings"]
  G --> B
```

## Search Flow

Search is implemented in `_search_flow()` + `_collect_search_hits()`.

### Search steps
1. User enters keyword and page depth.
2. Fetch albums from all sources and configured categories.
3. Compute fuzzy score for each album name.
4. Filter by threshold (`score >= 0.45`).
5. Deduplicate and sort results by score/year/name.
6. Show numbered table for selection.
7. For each selected hit, switch scraper context and run album download flow.

```mermaid
flowchart TD
    A["Enter keyword + depth"] --> B["Collect albums from each scraper"]
    B --> C["Compute fuzzy score"]
    C --> D{"score >= 0.45?"}
    D -- "no" --> E["discard"]
    D -- "yes" --> F["keep hit"]
    F --> G["dedupe by source + URL"]
    G --> H["sort hits"]
    H --> I["render numbered results"]
    I --> J["user selection"]
    J --> K["_download_album_flow per selected result"]
```

## Concurrency Model

### Current model
- Uses `ThreadPoolExecutor` in `HTTPDownloader.download_concurrent`.
- One future per song; completion consumed via `as_completed`.
- Shared structures:
  - `results[]` for indexed outcomes.
  - `pending_indices` for fallback tracking.
  - `Queue` slot pool for stable tqdm row positions.
  - `_state_lock` for atomic `.download_state.json` updates.
- If concurrent orchestration or any worker fails, remaining songs fall back to sequential download.

Note: UI shows progress bars during download; the main menu loop waits until current download batch completes.

```mermaid
flowchart LR
  A["App worker thread"] --> B["download_concurrent"]
    B --> C["ThreadPoolExecutor (N workers)"]
    C --> D["worker 1"]
    C --> E["worker 2"]
    C --> F["worker N"]

    D --> G["_download_with_progress"]
    E --> G
    F --> G

    G --> H["results[] + state updates"]
    H --> I{"any concurrent failure?"}
    I -- "yes" --> J["sequential fallback for pending"]
    I -- "no" --> K["return all results"]
    J --> K
```

## Resume Download Flow

Resume behavior is implemented in `_attempt_download()`.

### Resume rules
1. If final output file exists and size > 0:
   - skip download
   - mark state as completed
2. Else if `.part` exists:
   - set `Range: bytes=<existing_size>-`
   - if server returns `206`, continue append mode and mark progress as `resumed`
   - if server ignores range (`200`) or returns `416`, restart from beginning
3. Persist `.download_state.json` entries before and after transfer.
4. On success, rename `.part` to final file, apply tags, and mark completed.

```mermaid
flowchart TD
    A["Start _attempt_download"] --> B{"Final file exists?"}
    B -- "yes" --> C["Skip and set completed=true"]
    B -- "no" --> D{".part exists?"}

    D -- "yes" --> E["Send GET with Range header"]
    D -- "no" --> F["Send normal GET"]

    E --> G{"HTTP 206?"}
    G -- "yes" --> H["Resume append mode"]
    G -- "no" --> I["Restart from byte 0"]

    F --> J["Write from start"]
    H --> K["Write chunks + update progress"]
    I --> J
    J --> K

    K --> L["Rename .part -> final"]
    L --> M["Apply ID3 tags"]
    M --> N["Update .download_state.json completed=true"]
```
