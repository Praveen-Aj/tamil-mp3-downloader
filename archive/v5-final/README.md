# V5.0.0 Final Release Archive

This directory serves as the immutable archival package for the **V5.0.0 Release** of Tamil MP3 Downloader on branch `feature/library-source-foundation`.

## Contents

- `RELEASE_MANIFEST.json`: Machine-readable metadata describing all completed V5 phases, metrics, and verification results.
- `schema_v5.sql`: Frozen SQLite DDL dump representing the complete production schema for V5.

## Summary of Phases

1. **V5.1 — Database Foundation**: Multi-entity schema with tables for `movies`, `artists`, `movie_actors`, `movie_composers`, `song_artists`, `song_movies`, `charts`, `chart_entries`, `playlists`, `playlist_items`, `user_song_metadata`.
2. **V5.2 — FTS5 Search & Filtering**: Sub-15ms full-text search across 50,000 synthetic records and SQL AST-based filter compositions.
3. **V5.3 — Movies Discovery**: Regional catalog scraping, tracklist discovery, and deduplicated bulk "Download Missing".
4. **V5.4 — Artists & People**: Multi-role personnel catalog (Music Directors, Singers, Actors) with dedicated discography views.
5. **V5.5 — Curated Charts & Top 100**: Live iTunes Tamil Top Hits and evergreen classics with rank trends (▲, ▼, NEW, ＝).
6. **V5.6 — Playlists & Favorites**: User collections, 1-5 star ratings, favorites, and URL playlist importer with canonical deduplication.
7. **V5.7 — Artwork & UI Polish**: Asynchronous multi-tier artwork caching (LRU memory + SHA256 disk), ID3 APIC extraction, and design system polish.
