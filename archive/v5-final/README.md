# V5.0.0 Final Release Archive

This directory serves as the immutable, self-contained archival package for the **V5.0.0 Release** of Tamil MP3 Downloader on branch `feature/library-source-foundation`.

## Archival Package Structure

- `RELEASE_MANIFEST.json`: Machine-readable metadata describing all completed V5 phases, metrics, test results, and verification results.
- `schema_v5.sql`: Frozen SQLite DDL dump representing the complete production schema for V5.
- `docs/`: Complete phase specifications and audits:
  - `V5_FINAL_VALIDATION.md`: Comprehensive release audit and validation matrix.
  - `V5_REAL_WORLD_DATA_COVERAGE_AUDIT.md`: Real-world regional catalog, artist deduplication, and Top 100 coverage report.
  - `v5-architecture.md`: Architectural specification and data flow diagrams.
  - `v5.1-database-migration.md`: Multi-entity relational schema foundation.
  - `v5.2-search-filtering.md`: FTS5 search engine and AST filters.
  - `v5.3-movies.md`: Movie catalog scraping and deduplicated download missing.
  - `v5.4-artists-people.md`: Music directors, singers, and actors exploration.
  - `v5.5-charts.md`: Apple Music / iTunes Top 100 Tamil charts and evergreen feeds.
  - `v5.6-playlists.md`: Playlist management, 1-5 star ratings, and external import.
  - `v5.7-final-ui.md`: Artwork caching, ID3 APIC extraction, and design system polish.
- `screenshots/`: 10 high-resolution screenshots capturing all primary application views:
  - `01_dashboard_with_artwork.png`: Modern music-oriented dashboard with hero metrics and quick actions.
  - `02_movies_with_posters.png`: Movie catalog with visual poster artwork and year badges.
  - `03_movie_detail_artwork.png`: Movie detail modal with full tracklist and Download All/Missing.
  - `04_artists_portraits.png`: Multi-role artist catalog with role badges and soundtrack counts.
  - `05_artist_detail_artwork.png`: Comprehensive artist discography breakdown (Composer vs Singer tracks).
  - `06_charts_with_artwork.png`: Chart feeds with snapshot dates and track metrics.
  - `07_chart_detail_artwork.png`: Tamil Top 100 chart entries with rank trends and download states.
  - `08_playlists_with_artwork.png`: User playlists catalog with total track counts.
  - `09_playlist_detail_artwork.png`: Playlist detail view with drag/drop reordering and individual track downloads.
  - `10_downloaded_songs_artwork.png`: Authoritative downloaded songs manager with exact file sizes, sorting, and playback.
- `config/`:
  - `release_config.json`: Baseline production configuration and provider defaults.
- `tests/`:
  - `TEST_VERIFICATION_REPORT.md`: Comprehensive test verification summary covering all 294 selected tests with 0 failures.

## Summary of Phases

1. **V5.1 — Database Foundation**: Multi-entity schema with tables for `movies`, `artists`, `movie_actors`, `movie_composers`, `song_artists`, `song_movies`, `charts`, `chart_entries`, `playlists`, `playlist_items`, `user_song_metadata`.
2. **V5.2 — FTS5 Search & Filtering**: Sub-15ms full-text search across 50,000 synthetic records and SQL AST-based filter compositions.
3. **V5.3 — Movies Discovery**: Regional catalog scraping, tracklist discovery, and deduplicated bulk "Download Missing".
4. **V5.4 — Artists & People**: Multi-role personnel catalog (Music Directors, Singers, Actors) with dedicated discography views.
5. **V5.5 — Curated Charts & Top 100**: Live iTunes Tamil Top Hits and evergreen classics with rank trends (▲, ▼, NEW, ＝).
6. **V5.6 — Playlists & Favorites**: User collections, 1-5 star ratings, favorites, and URL playlist importer with canonical deduplication.
7. **V5.7 — Artwork & UI Polish**: Asynchronous multi-tier artwork caching (LRU memory + SHA256 disk), ID3 APIC extraction, and design system polish.
