# Architecture Guide

This document is the authoritative developer blueprint for the **Tamil MP3 Downloader** modular architecture.

## Overview

The application shifted from a legacy "search-and-download" flow to a persistent, library-centric model (Phase 1–12 of the v4 redesign). 
Instead of users interacting directly with web scrapers to download files, all discovery is persisted to a local SQLite database (the Canonical Library). Users browse the library, select tracks, and schedule them for download.

### Core Data Flow

```text
Sources
  ↓ (Scraping)
Discovery Pipeline
  ↓ (Deduplication & Canonical Identity)
SQLite Canonical Library (Source of Truth)
  ↓ (User Selection & Download Registry)
Download Planner
  ↓ (Quality upgrades & Fallbacks)
Download Queue
  ↓ (Concurrent execution)
Filesystem (.mp3 with ID3 tags)
```

## 1. The Canonical Library (SQLite)

The backend is built around a thread-safe `SQLiteDatabase` manager utilizing `sqlite3`.

- `LibrarySong`: Represents a unique audio track. Features a deterministic `canonical_hash` (stripping special characters, quality suffixes, and case differences) to collapse duplicates across categories and sources.
- `SongSource`: Represents a unique variant of a song available on a specific source website. Contains `source_url`, `download_reference` (for dynamic signed URL resolution), `quality_kbps`, and `file_size_bytes`.
- `SongState`: Tracks ownership (`DISCOVERED`, `QUEUED`, `DOWNLOADING`, `OWNED`, `FAILED`).

## 2. Source Health Registry

The `SourceRegistry` maintains the active status and reliability scores of external sources.

- **Sources:** MassTamilan, Tamilmp3 (Kuttyweb), FriendsTamilMP3.
- **Failover:** If a primary domain goes down, the registry dynamically shifts to configured backup domains.
- **Reliability Scoring:** Sources gain and lose reliability points based on real-time HTTP failures, influencing the download planner's fallback choices.

## 3. Discovery Pipeline

The `DiscoveryPipeline` is responsible for querying enabled sources, resolving raw objects into deterministic canonical hashes, and bulk inserting them into SQLite.
- It operates safely in a background thread.
- **Deduplication:** A song found in both "Top 2026 Hits" and "Actor Hits" on two different sources is collapsed into a single `LibrarySong` with two `SongSource` variants.

## 4. Download Planning

The `DownloadPlanner` bridges the SQLite library and the download queue.
- **Quality Overrides:** Automatically upgrades a user's request to 320kbps if a better `SongSource` variant is available across the deduplicated dataset.
- **Owned Skipping:** Safely ignores requests for songs already marked as `OWNED`.
- **Precedence Logic:** Sources are ranked by:
  1. Availability (is the source healthy?)
  2. Audio Quality (highest kbps first)
  3. User Preferences (configured source priority)
  4. Reliability Score (track record of success)
  5. File size (larger files preferred when quality metadata is ambiguous)

## 5. User Interface (CustomTkinter)

The UI is highly decoupled and modular, housed in `ui/`.

- **app.py:** Canonical entry point. Mounts the sidebar and dynamically hosts views.
- **services/library_service.py:** The unified interface bridging the GUI to the database and background threads. Implements locks (`threading.RLock`) to ensure GUI event loop isolation.
- **views/**: Discrete modules for Dashboard, Discover, Library, Downloads, Sources, Import, and Settings.
- **components/**: Reusable widgets (e.g., `SongTable`).

## 6. Background Threads & Concurrency

- **No blocking the main thread.** Operations such as `execute_downloads`, `run_discovery`, and `check_source_health` execute via `threading.Thread`.
- Results are marshalled back to the UI via Tkinter's `self.after(0, callback)`.
- Concurrent HTTP downloads run using `ThreadPoolExecutor` within the `HTTPDownloader`.

## 7. Automated Testing Strategy

The `tests/` directory is strictly partitioned:
1. **Unit & Integration:** Mocks the HTTP scrapers entirely. Tests SQLite deduplication, thread-safety, download planner algorithms, and UI flow correctness.
2. **Live Scraper Protocol (`@pytest.mark.live`):** Connects to the real websites to ensure network payloads and dynamic token generators (e.g., Tamilmp3 `token.php`) remain intact.
