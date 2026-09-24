# Next Version Feature Roadmap: Tamil Music Discovery, Download & Library Management

## Executive Summary
This document defines the formal architectural roadmap and feature backlog for future versions of the **Tamil MP3 Downloader**.
The current application version focuses strictly on **core download stability, filesystem truth reconciliation, and reliable universal URL acquisition**.
The features specified below are planned for the next major release milestone (v5.0.0+) and must not be implemented during current stabilization phases.

---

## Roadmap Categories & Feature Specifications

### Category A: Movie / Album Based Download

#### Feature A.1: Movie Catalog Discovery & Bulk Album Acquisition
- **User Use Case:** A user searches for a movie (e.g., *"Kathi"*, *"Vikram"*, *"3"*, *"Leo"*) and wants to preview the movie's album metadata and download all songs with a single click.
- **Expected Behavior:**
  - Typing a movie title displays rich movie metadata (banner artwork, release year, music director, director, lead actors, total track count).
  - Displays complete tracklist showing individual song titles, singers, lyricists, and durations.
  - One-click **"Download Entire Album"** queues all tracks with automated source resolution and concurrency management.
  - Automatically identifies tracks already downloaded in the local library, indicating `Downloaded` status and avoiding duplicate downloads.
- **Required Data:** Movie title, year, composer/music director, artwork image URL, track list with audio source URLs/identifiers, duration, singers.
- **Potential Dependencies:** Regional scrapers (Isaimini, MassTamilan, TamilMP3), MusicBrainz API, Spotify Album API, `mutagen` for album art embedding.
- **UI Implications:** Dedicated "Movie / Album" detail view with header artwork, release year pill, composer badge, and tracklist table with individual + bulk download controls.
- **Backend Implications:** Album-level batch planner resolving tracks concurrently and creating grouped download batches.
- **Database Implications:** Add `albums` and `movies` relational tables or expand `LibrarySong` schema with foreign keys (`album_id`, `movie_id`, `track_position`).
- **Search/Indexing Implications:** FTS5 full-text index on movie title, alternative phonetic titles (e.g., "Kaththi" vs "Kathi").
- **Testing Requirements:** Deterministic integration test simulating album metadata scraping, track discovery, bulk download execution, and duplicate skip logic.
- **Dependencies/Blockers:** Requires stable scraper endpoints for album-level indexes.
- **Open Questions:** How to handle movies with multiple soundtrack releases (e.g., Original vs Deluxe vs Extended OST versions)?

---

### Category B: Singer / Artist Based Download

#### Feature B.1: Artist Discography & Filtered Track Acquisition
- **User Use Case:** A user searches for a specific composer or singer (e.g., *"Show songs by A.R. Rahman"*, *"Download all Anirudh songs"*, *"Songs sung by Shreya Ghoshal"*).
- **Expected Behavior:**
  - Displays artist profile with photo, biography summary, role badges (Composer, Singer, Lyricist), and grouped discography (Albums, Hit Singles, Collabs).
  - Allows filtering artist tracks by year, popularity, or role.
  - Provides multi-select and "Download All Hits" action.
- **Required Data:** Artist canonical name, aliases, roles, profile image, discography track mappings.
- **Potential Dependencies:** Spotify Artist Metadata API, Last.fm API, regional site artist directories.
- **UI Implications:** "Artists" navigation tab with artist search, grid of artist photo cards, and filtered tracklist table.
- **Backend Implications:** Aggregation service grouping canonical library songs by artist tags; support for multi-artist splitting (e.g. "Anirudh Ravichander, Jonita Gandhi").
- **Database Implications:** `artists` table with `song_artists` junction table supporting many-to-many relationships and artist roles.
- **Search/Indexing Implications:** Artist name phonetic matching (Soundex / Metaphone) to resolve transliteration variances (e.g., "Rahman", "A.R. Rahman", "AR Rahman").
- **Testing Requirements:** Unit tests for multi-artist delimiter parsing and database junction query performance.
- **Dependencies/Blockers:** Scraper support for artist listing pages.
- **Open Questions:** Standardizing transliterated Tamil artist names against Latin naming conventions.

---

### Category C: Top Songs & Curated Rankings

#### Feature C.1: Periodic Charts & Trending Music Discovery
- **User Use Case:** A user wants to explore what is currently popular in Tamil music without searching for a specific song (e.g., *"Top 100 Weekly"*, *"Top 100 Monthly"*, *"Trending Hits 2026"*).
- **Expected Behavior:**
  - Displays dynamic chart lists with rank numbers, rank change indicators (▲, ▼, NEW), play preview buttons, and quick download icons.
  - Clearly attributes chart source and timestamp (e.g., "Apple Music Tamil Top 100 - Updated Sep 2026").
  - Users can select the top 10, 25, 50, or 100 songs to download in bulk.
- **Required Data:** Chart title, rank index, track title, artist, movie/album, stream provider reference, chart update date.
- **Potential Dependencies:** Spotify Billboard/Viral Charts API, Apple Music RSS feeds, YouTube Music Tamil Trending charts.
- **UI Implications:** "Top Songs" navigation tab with tabbed sub-views (Weekly, Monthly, Yearly, Trending) and ranking badges.
- **Backend Implications:** Periodic background chart scraper / aggregator with TTL caching to minimize network usage.
- **Database Implications:** `charts` and `chart_entries` tables storing snapshot history.
- **Search/Indexing Implications:** Fast rank sorting and filter by year/genre.
- **Testing Requirements:** Mock chart feed test validating chart ingestion, rank preservation, and bulk download enqueuing.
- **Dependencies/Blockers:** Reliable third-party chart data endpoint without strict authentication barriers.
- **Open Questions:** How frequently should chart snapshots refresh (e.g. daily vs weekly)?

---

### Category D: Advanced Multi-Field Search

#### Feature D.1: Unified Omnibox Search
- **User Use Case:** A user enters a query combining multiple entities (e.g., *"Anirudh Kathi"*, *"SPB 1980s Ilaiyaraaja"*, *"Sid Sriram Love"*) and expects accurate matching.
- **Expected Behavior:**
  - Tokenizes input query across title, movie, singer, composer, year, and genre.
  - Supports search modes: Exact, Prefix, Fuzzy (Levenshtein / Trigram), and Multi-field keyword matching.
  - Real-time debounced instant suggestions dropdown as the user types.
- **Required Data:** Normalized search tokens for all songs, albums, and artists in the database.
- **Potential Dependencies:** SQLite FTS5 extension.
- **UI Implications:** Top navigation persistent search omnibox with clear button, filter pills, and search result grouping (Movies, Songs, Artists).
- **Backend Implications:** Query parser identifying year ranges (e.g. "1990s"), artist names, and song titles.
- **Database Implications:** SQLite `songs_fts` virtual table using FTS5 with BM25 ranking.
- **Search/Indexing Implications:** SQLite FTS5 trigger synchronization on INSERT/UPDATE/DELETE.
- **Testing Requirements:** Unit test suite covering 50+ real Tamil search phrases, transliterations, and typo tolerance.
- **Dependencies/Blockers:** SQLite compiled with FTS5 support (standard in Python 3.12).
- **Open Questions:** Balancing fuzzy threshold to prevent false positive matches on short 3-letter Tamil movie titles (e.g., "3", "I", "96").

---

### Category E: Sorting

#### Feature E.1: Multi-Column Library Sorting
- **User Use Case:** In any view (Downloaded Songs, Library, Albums), user wants to order songs by title, artist, movie, year, date downloaded, file size, duration, bitrate, or popularity.
- **Expected Behavior:**
  - Clickable column headers with ascending/descending toggle arrows.
  - Secondary tie-breaker sorting (e.g., primary: Album A-Z, secondary: Track Number ascending).
  - Retains sort preference across sessions in `settings.json`.
- **Required Data:** Track attributes (`title`, `artist`, `album`, `year`, `downloaded_at`, `file_size_bytes`, `duration_seconds`, `quality_kbps`).
- **Potential Dependencies:** None (native SQLite and Python sort).
- **UI Implications:** Interactive column headers with active sort glyphs.
- **Backend Implications:** Optimized SQL `ORDER BY` clauses for paginated database queries.
- **Database Implications:** Composite indexes on `(state, year)`, `(state, title)`, `(state, artist)`.
- **Search/Indexing Implications:** Case-insensitive collation (`COLLATE NOCASE`).
- **Testing Requirements:** Functional tests verifying sort ordering for all supported criteria.
- **Dependencies/Blockers:** None.
- **Open Questions:** Standardizing year sorting when release year is unknown or null.

---

### Category F: Composable Filters

#### Feature F.1: Faceted Filter Panel
- **User Use Case:** A user wants to narrow down songs (e.g., "Show 320 kbps songs from 2020-2025 composed by Anirudh that are Downloaded").
- **Expected Behavior:**
  - Slide-out or sticky filter bar with multi-select checkboxes for Bitrate (128, 192, 320), Decades (80s, 90s, 00s, 10s, 20s), Download State, and Composers.
  - Active filter chips with individual remove "✕" and "Clear All" button.
  - Instant count of matching items updated dynamically.
- **Required Data:** Facet counts for distinct values across the library.
- **Potential Dependencies:** None.
- **UI Implications:** Compact filter bar above table or collateral sidebar filter panel.
- **Backend Implications:** Dynamic SQL query builder constructing parametrized `WHERE` clauses.
- **Database Implications:** Appropriate indexes on filterable columns.
- **Search/Indexing Implications:** Fast facet count generation (`GROUP BY`).
- **Testing Requirements:** Unit tests for query builder edge cases (combining 5+ filter dimensions).
- **Dependencies/Blockers:** None.
- **Open Questions:** UI density in standard window sizes without vertical clutter.

---

### Category G: User Ratings & Favorites

#### Feature G.1: 5-Star Rating & Favorites System
- **User Use Case:** A user rates songs from 1 to 5 stars or clicks a heart icon (❤️) to mark favorites, creating instant smart playlists.
- **Expected Behavior:**
  - Interactive star rating widget in song rows and player view.
  - Heart icon toggle for "Favorite" status.
  - Dedicated "Favorites" tab in sidebar displaying all starred songs.
- **Required Data:** `rating` (integer 1-5, NULL if unrated), `is_favorite` (boolean), `favorited_at` (timestamp).
- **Potential Dependencies:** None.
- **UI Implications:** Star widget with hover effects; heart icon button in table rows.
- **Backend Implications:** Service methods `set_song_rating(song_id, rating)` and `toggle_favorite(song_id)`.
- **Database Implications:** Add `rating` (TINYINT) and `is_favorite` (BOOLEAN) columns to `songs` table with index.
- **Search/Indexing Implications:** Fast filtering `WHERE is_favorite = 1`.
- **Testing Requirements:** Functional tests testing star updates, favorite toggling, and smart view filtering.
- **Dependencies/Blockers:** None.
- **Open Questions:** Keeping user personal ratings separate from external popularity/streaming play counts.

---

### Category H: Playlists & Custom Collections

#### Feature H.1: User Playlist Creation & Management
- **User Use Case:** A user creates custom playlists (e.g., *"Gym Tamil Hits"*, *"Ilaiyaraaja Melody Night"*, *"Road Trip"*), adds/removes songs, and exports as M3U8.
- **Expected Behavior:**
  - "New Playlist" modal with custom name, description, and cover image.
  - Right-click song menu -> "Add to Playlist" -> select target playlist.
  - Drag-and-drop or up/down ordering of tracks within playlist.
  - "Export as M3U8" to play on external devices or automotive systems.
- **Required Data:** Playlist metadata, track sequence numbers, file paths.
- **Potential Dependencies:** M3U8 playlist writer.
- **UI Implications:** "Playlists" section in sidebar with list of playlists and creation button.
- **Backend Implications:** Playlist service with add/remove/reorder track methods.
- **Database Implications:** `playlists` table and `playlist_tracks` junction table (`playlist_id`, `song_id`, `position`, `added_at`).
- **Search/Indexing Implications:** None.
- **Testing Requirements:** Full functional test for playlist CRUD, track reordering, and M3U8 file generation.
- **Dependencies/Blockers:** None.
- **Open Questions:** Synchronizing playlist tracks when an underlying song file is deleted from disk.

---

### Category I: Music Metadata & ID3 Enrichment

#### Feature I.1: Comprehensive Tagging & Artwork Embedding
- **User Use Case:** Ensure all downloaded MP3s have studio-grade metadata (high-res cover art, release year, album artist, lyricist, genre, track numbers) compatible with Apple Music, VLC, Windows Media Player, and car infotainment systems.
- **Expected Behavior:**
  - Automatic embedding of ID3v2.3/ID3v2.4 tags using `mutagen`.
  - Downloads and embeds square album art (minimum 500x500 px, JPEG).
  - "Edit Metadata" modal allowing manual correction of song details.
- **Required Data:** Song title, artist, album, composer, lyricist, year, genre, track number, disc number, cover art image binary.
- **Potential Dependencies:** `mutagen`, `Pillow` (PIL) for image resizing/cropping.
- **UI Implications:** "Edit Song Metadata" dialog accessible via right-click or song detail view.
- **Backend Implications:** ID3 rewrite engine that safely re-tags files in-place without corrupting audio frames.
- **Database Implications:** Store rich metadata attributes in SQLite `songs` table.
- **Search/Indexing Implications:** None.
- **Testing Requirements:** Integration tests validating mutagen tag reading and binary frame integrity after tag modification.
- **Dependencies/Blockers:** None.
- **Open Questions:** Handling non-MP3 formats (e.g. M4A/AAC, FLAC, Opus) tagging uniformly.

---

### Category J: Library Intelligence & Health Scanner

#### Feature J.1: Automatic Library Integrity & Duplicate Audit
- **User Use Case:** The user moves files on disk, deletes songs externally, or accumulates multiple duplicate versions of the same song at different bitrates, and wants the library to automatically clean up and optimize itself.
- **Expected Behavior:**
  - Background or on-demand **"Library Health Scan"**.
  - Identifies missing physical files, broken paths, zero-byte files, and duplicate audio hashes.
  - One-click **"Upgrade 128k to 320k"** scanning library for lower quality tracks with available high-bitrate sources.
- **Required Data:** File checksums, acoustic fingerprints (Chromaprint / AcoustID where applicable), file existence checks.
- **Potential Dependencies:** `pyacoustid` (optional for acoustic fingerprinting), `hashlib`.
- **UI Implications:** "Library Health & Maintenance" card in Settings or Library view with health score and fix buttons.
- **Backend Implications:** Multi-threaded filesystem scanner checking disk paths against SQLite rows.
- **Database Implications:** Track file hashes (`sha256`) and file modification timestamps.
- **Search/Indexing Implications:** None.
- **Testing Requirements:** Deterministic integration test moving, renaming, and deleting files, verifying that the scanner detects and repairs every mismatch.
- **Dependencies/Blockers:** None.
- **Open Questions:** Performance of scanning 50,000+ files on slower external hard drives.

---

### Category K: Advanced Download Manager Experience

#### Feature K.1: Prioritized Queue, Speed Control & Granular Diagnostics
- **User Use Case:** User downloads 50 songs and wants to pause, resume, change queue order, limit download speed, and view precise per-source connection diagnostics.
- **Expected Behavior:**
  - Pause, Resume, and Cancel buttons per download row.
  - Drag-and-drop or Move Up / Move Down queue prioritization.
  - Real-time download speed graph (KiB/s, MiB/s) and estimated time remaining (ETA).
  - Detailed tooltip/dialog showing exact HTTP response codes, provider fallbacks, and retry count.
- **Required Data:** Chunk transfer rates, bytes received, total bytes, connection start time, retry log.
- **Potential Dependencies:** Thread-safe chunk streaming hooks.
- **UI Implications:** Modern download queue table with progress bars, speed pills, and pause/resume controls.
- **Backend Implications:** Cancellable download workers with `threading.Event` tokens.
- **Database Implications:** `downloads` table tracking `paused_at`, `bytes_downloaded`, `eta_seconds`.
- **Search/Indexing Implications:** None.
- **Testing Requirements:** Functional tests for pause/resume state transitions and queue priority reordering.
- **Dependencies/Blockers:** HTTP servers supporting `Range` headers for pause/resume.
- **Open Questions:** Resuming chunk streams from providers that dynamically generate expiring tokens.

---

### Category L: Modern Music Discovery UI / Navigation Architecture

#### Feature L.1: Unified Music Hub Navigation
- **User Use Case:** The desktop interface feels like a modern music discovery and player hub (similar to Spotify / Apple Music) rather than an engineering utility.
- **Expected Behavior:**
  - Sidebar hierarchy:
    - **DISCOVER:** Dashboard, Top Songs, Movies, Artists, New Releases
    - **COLLECTION:** Downloaded Songs, My Library, Favorites, Playlists
    - **TRANSFERS:** Downloads (with active download badge count)
    - **SYSTEM:** Settings, Help
  - Responsive cards with subtle hover animations, glassmorphism accents, and color harmony.
- **Required Data:** Aggregated counts across categories.
- **Potential Dependencies:** `customtkinter`, curated color palette in `ui/theme.py`.
- **UI Implications:** Complete navigation restructure mounting unified views.
- **Backend Implications:** Unified navigation coordinator and event bus.
- **Database Implications:** None.
- **Search/Indexing Implications:** None.
- **Testing Requirements:** GUI startup and view-switching regression suite.
- **Dependencies/Blockers:** Should be executed ONLY after Categories A-K backend engines are finalized.
- **Open Questions:** Ensuring optimal rendering performance with large image collections in Tkinter.

---

## 3. Implementation Phasing & Preconditions

| Phase | Focus Milestone | Preconditions | Target Deliverables |
| :---: | :--- | :--- | :--- |
| **Current** | **Download Pipeline Stabilization** | None. In progress now. | 100% reliable single-song and playlist downloads, filesystem truth, multi-tier tests. |
| **Phase 1** | **Movie & Album Engine** | Core downloads verified. | Movie catalog scraper, album view, bulk download. |
| **Phase 2** | **Artist & Discography Engine** | Movie engine completed. | Artist profiles, singer/composer filters. |
| **Phase 3** | **Search & Smart Filters** | Category A & B data in DB. | Omnibox FTS5 search, multi-field faceted filtering. |
| **Phase 4** | **Curated Charts & Top Songs** | Search & scraper architecture ready. | Top 100 Weekly/Monthly charts with bulk acquisition. |
| **Phase 5** | **Playlists, Ratings & Library Intelligence** | Local library established. | Playlists, 5-star ratings, M3U8 export, duplicate auditor. |
| **Phase 6** | **Discovery UI Polish & Player Experience** | All backend services functional. | Full navigation redesign and modern desktop UX. |
