# V6.0 Architecture & Service Boundary Specification

**Status:** Completed  
**Branch:** `feature/v6-web-migration`  
**Baseline HEAD:** `bf32eba`  
**Reference Document:** `V6_WEB_MIGRATION_PLAN.md`  

---

## 1. Executive Summary & Purpose

Phase **V6.0 (Architecture & Extraction)** establishes the clean separation between presentation and business logic required to transition the Tamil MP3 Downloader from a Tkinter/CustomTkinter desktop application to a modern web application (React + TypeScript frontend powered by a FastAPI REST and WebSocket backend).

As mandated by **Rule 4, Rule 5, Rule 6**, and the central guiding principle of `V6_WEB_MIGRATION_PLAN.md`:

> **V6 is primarily a presentation-layer transformation, NOT a business-logic rewrite.**

The proven V5 core systems—including canonical song identity, SQLite schema, FTS5 search engine, provider failover registry, download planner, concurrent job manager, URL resolver, and filesystem reconciliation—are preserved as the single source of truth.

---

## 2. Target V6 System Architecture

```text
┌────────────────────────────────────────────────────────┐
│             Web Client (React / TypeScript)             │
│  - Lucide Icons    - Tailwind Obsidian Theme            │
│  - Persistent HTML5 Audio Player                       │
│  - Real-time WebSocket Download & Import Monitor       │
└───────────────────────────┬────────────────────────────┘
                            │ HTTP REST / WebSocket
                            ▼
┌────────────────────────────────────────────────────────┐
│                   FastAPI Backend                      │
│  - /api/system       - /api/songs      - /api/movies    │
│  - /api/artists      - /api/charts     - /api/playlists │
│  - /api/downloads    - /api/imports    - /api/settings  │
│  - /api/artwork      - /ws/events (WebSocket Bus)      │
└───────────────────────────┬────────────────────────────┘
                            │ In-Process Service Calls
                            ▼
┌────────────────────────────────────────────────────────┐
│         Extracted Core Service Layer (`library`)        │
│  - library.service.LibraryService (Authoritative)       │
│  - library.database.SQLiteDatabase                     │
│  - library.planner.DownloadPlanner                     │
│  - library.registry.DownloadRegistry                   │
│  - library.artwork.ArtworkManager                      │
│  - library.jobs.job_manager.ImportJobManager           │
│  - library.charts.ChartDiscoveryService                │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
               ▼                          ▼
┌───────────────────────────┐  ┌─────────────────────────┐
│     Filesystem Storage    │  │    External Providers   │
│  - downloads/*.mp3        │  │  - MassTamilan           │
│  - cache/artwork/         │  │  - Tamilmp3, Isaimini    │
│  - data/library.db        │  │  - Spotify / YouTube API │
└───────────────────────────┘  └─────────────────────────┘
```

---

## 3. Extraction & Decoupling Boundaries

### 3.1 Extraction of `LibraryService`
Prior to V6.0, `LibraryService` was located under `ui/services/library_service.py` despite containing zero Tkinter code.

* **Extracted Location:** [`library/service.py`](file:///c:/Users/Praveen/Downloads/Python%20Scripts/tamil-mp3-downloader/library/service.py)
* **Package Export:** [`library/__init__.py`](file:///c:/Users/Praveen/Downloads/Python%20Scripts/tamil-mp3-downloader/library/__init__.py) (`from library import LibraryService`)
* **Backward Compatibility Adapter:** [`ui/services/library_service.py`](file:///c:/Users/Praveen/Downloads/Python%20Scripts/tamil-mp3-downloader/ui/services/library_service.py) re-exports all symbols from `library.service`. All desktop views and legacy tests continue functioning without modification.

### 3.2 Desktop UI Isolation
Tkinter, CustomTkinter, and PIL CTkImage objects are strictly isolated within the `ui/` directory:
* `ui/views/` (Desktop views: songs, movies, artists, charts, playlists, downloads, settings)
* `ui/components/` (Tkinter widgets: sidebar, song table, status bar)
* `ui/dialogs/` (Tkinter dialogs: song details, plan preview)
* `ui/services/artwork_service.py` (Desktop CTkImage wrapper around `library.artwork.ArtworkManager`)
* `ui/theme.py` (CTk color tokens and font helpers)

The web backend does NOT import `ui`.

---

## 4. Filesystem & Audio Streaming Boundary

Because web browsers cannot execute local system commands (`os.startfile`) or access local Windows filesystem paths (`C:\Users\...`), the FastAPI backend exposes managed endpoints:

1. **HTTP 206 Partial Content Audio Streaming:**
   - Endpoint: `GET /api/songs/{id}/stream`
   - Supports HTTP `Range: bytes=start-end` requests for instant HTML5 `<audio>` playback, scrubbing, and seeking.
   - Authoritative audio files are resolved through `library.service.get_song(song_id).file_path`.
2. **Artwork Serving:**
   - Endpoint: `GET /api/artwork/{category}/{entity_id}`
   - Categories: `song`, `movie`, `artist`, `chart`, `playlist`.
   - Returns cached binary image (`image/jpeg` or `image/png`) or generates dynamic SVG/PNG fallbacks via `library.artwork.ArtworkFallbackGenerator`.
3. **Directory Open (Localhost Only):**
   - Endpoint: `POST /api/songs/{id}/open-folder`
   - Allowed only when client connects from `127.0.0.1` / `localhost`.
4. **Security & Path Traversal Prevention:**
   - Any file served by the backend is verified to reside within the configured download directory using `Path(path).resolve().is_relative_to(download_dir.resolve())`.

---

## 5. Real-Time WebSocket Event Protocol

`LibraryService` already implements a thread-safe observer pattern with `add_progress_listener(callback)`.

The FastAPI WebSocket router (`/ws/events`) attaches an asynchronous broadcast bridge to this callback bus:

```json
{
  "event": "download.progress",
  "data": {
    "song_id": 42,
    "track_title": "Arabic Kuthu",
    "artist": "Anirudh Ravichander",
    "status": "downloading",
    "progress_percent": 68.5,
    "speed_mbps": 4.2,
    "eta_seconds": 3,
    "error": null
  }
}
```

Supported WebSocket events:
* `download.started`
* `download.progress`
* `download.completed`
* `download.failed`
* `import.started`
* `import.progress`
* `import.completed`
* `library.changed`

---

## 6. Authentication & Security Strategy

* **Stage 1 (Localhost):** Zero authentication. Complete trust for single-user local machine operation.
* **Stage 2 (LAN / Private Network):** Configurable API Bearer token in `config/settings.json` (`V6_API_TOKEN`). If configured, web clients supply `Authorization: Bearer <token>` or `?token=<token>` for WebSockets. Local directory opening endpoints (`open-folder`) are automatically disabled for non-loopback connections.
* **Stage 3 (Hosted / Remote):** Optional lightweight session authentication with Argon2 password hashing if internet exposure is required in future phases.

---

## 7. Frontend Architecture Decision

* **Framework:** React 18+ with TypeScript
* **Tooling:** Vite for sub-second hot reload and optimized production bundles
* **Styling:** Tailwind CSS with modern dark glassmorphic styling (Obsidian slate `#0d1117`, card surface `#161b22`, accent emerald/cyan `#10b981`)
* **State Management:** React Query (TanStack Query) for server state caching + lightweight Zustand for active playback and UI state
* **Icons:** Lucide React

---

## 8. Verification & Backward Compatibility

* **Test Suite:** 294 unit and integration tests passing (0 failures).
* **Desktop GUI Tests:** All GUI tests pass with zero regressions.
* **Entry Point:** `main.py` verified to launch the desktop app without errors.
