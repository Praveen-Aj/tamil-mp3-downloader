# V6 Web Migration Plan — Tamil Music Discovery & Personal Library Manager

**Status:** Planning / Future Phase  
**Version:** V6 Web Baseline v1.0  
**Implementation status:** NOT STARTED  
**Start condition:** Only after all V5.x phases are complete and V5.7 has passed final validation  
**Current V5 branch:** `feature/library-source-foundation`  
**V6 target branch:** `feature/v6-web-migration`  
**Stable branch:** `main`

---

## 1. Purpose

V6 is a planned migration of the proven V5 desktop application into a web-based application.

This is **not** a full rewrite of the product's business logic.

The primary objective is:

> Replace the Tkinter presentation layer with a modern web UI while preserving the proven V5 domain, library, provider, discovery, search, download-planning, download-job, deduplication, and filesystem-reconciliation architecture wherever practical.

The final V6 architecture must be reviewed and may be revised at the end of V5.7 before implementation begins.

---

# 2. V5 → V6 Strategy

```text
V5.1 Database Foundation
        ↓
V5.2 Search / Filtering
        ↓
V5.3 Movies
        ↓
V5.4 Artists / Singers / Music Directors / Actors
        ↓
V5.5 Charts
        ↓
V5.6 Playlists / Ratings / Favorites
        ↓
V5.7 Artwork / Final UI Polish
        ↓
V5 FINAL RELEASE
        ↓
FULL V5 ARCHIVE / FREEZE
        ↓
V6 ARCHITECTURE REVIEW
        ↓
V6 WEB MIGRATION
```

V5 remains the stable desktop reference implementation.

V6 development must not damage the final V5 application.

---

# 3. Mandatory V5 Archive Before V6

Before V6 implementation starts, create a complete immutable archive of the final V5 application.

The archive should contain:

```text
archive/
└── v5-final/
    ├── source/
    ├── docs/
    ├── tests/
    ├── screenshots/
    ├── database/
    ├── configuration/
    ├── release-notes/
    └── V5_FINAL_VALIDATION.md
```

Also create a Git tag representing the final V5 state, for example:

`v5.7.0-final`

The exact version number can be decided at the end of V5.

The archive must remain unchanged throughout V6.

The archive must allow the team to reconstruct exactly what the final V5 desktop application contained.

---

# 4. V5 Final Release Gate

V6 must NOT begin merely because V5.7 code exists.

V5 must first pass a final release validation.

## Functional validation

Verify:

- Songs
- Movies
- Singers / Artists
- Music Directors / Composers
- Actors
- Search
- Filtering
- Sorting
- Charts
- Playlists
- Ratings
- Favorites
- Artwork
- URL import
- Playlist import
- Download All
- Download Missing
- Download Selected
- Retry
- Concurrent downloads
- Duplicate prevention
- Quality upgrade
- No quality downgrade
- Playback
- Open Folder
- Delete / remove behavior
- Settings
- Help

## Data validation

Verify:

- SQLite schema is consistent
- Canonical songs remain unique
- `song_sources` relationships are valid
- Movie/song many-to-many relationships are valid
- Artist/song relationships are valid
- Artist/movie relationships are valid
- Playlist relationships are valid
- Chart relationships are valid
- User metadata is preserved
- No unexpected orphan records exist
- No unintended cascade deletion of canonical songs/audio files

## Filesystem validation

Verify:

```text
Database state
      ↕
Physical filesystem
```

remain correctly reconciled.

Physical audio files must be checked, not inferred only from database state.

---

# 5. Branch Strategy

V5:

```text
main
│
└── feature/library-source-foundation
     ├── V5.4
     ├── V5.5
     ├── V5.6
     └── V5.7
```

After V5 finalization:

```text
main
│
├── V5 stable / archived reference
│
└── feature/v6-web-migration
```

Rules:

1. Never modify `main` directly.
2. V6 work must occur on the V6 branch or controlled V6 sub-branches.
3. V5 must remain recoverable.
4. V6 failure must never corrupt the final V5 implementation.
5. Do not delete working V5 functionality simply because V6 does not immediately need it.

---

# 6. Target V6 Architecture

Initial architecture proposal:

```text
                   Browser
                      │
                      │ HTTPS / HTTP
                      ▼
             React + TypeScript
                      │
               REST + WebSocket
                      │
                      ▼
                 FastAPI API
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
 Library Services  Download      Discovery
        │             │             │
        └─────────────┼─────────────┘
                      │
                      ▼
                   SQLite
                      │
                      ▼
                File System
```

This is a target architecture, not an implementation mandate.

The final technology choices must be reviewed at the end of V5.7.

---

# 7. Core Architectural Principle

The central V6 principle is:

> V6 is primarily a presentation-layer transformation, not a business-logic rewrite.

The following V5 systems should be reused wherever practical:

- Canonical library
- SQLite database layer
- Provider registry
- Discovery architecture
- Search / FTS5
- LibraryService
- DownloadPlanner
- DownloadJobManager
- ImportJobManager
- Filesystem reconciliation
- Duplicate detection
- Quality upgrade/no-downgrade logic
- URL resolution
- Provider abstractions

The main UI transformation is:

```text
V5:
Tkinter
   ↓
Library Services

V6:
React / TypeScript
   ↓
FastAPI
   ↓
Library Services
```

---

# 8. Database Boundary

The web frontend must NOT access SQLite directly.

Never:

```text
React → SQLite
```

Use:

```text
React
  ↓
FastAPI
  ↓
LibraryService
  ↓
Database
```

This creates a clean API boundary and allows the database implementation to evolve later if required.

SQLite should remain the initial V6 database unless the final architecture review determines that multi-user or hosted requirements justify another database.

---

# 9. API Layer

V6 should introduce an explicit FastAPI API layer.

Potential route groups:

```text
/api/songs
/api/movies
/api/artists
/api/search
/api/downloads
/api/imports
/api/playlists
/api/charts
/api/settings
/api/system
```

Potential project structure:

```text
api/
├── routes/
│   ├── songs.py
│   ├── movies.py
│   ├── artists.py
│   ├── charts.py
│   ├── playlists.py
│   ├── downloads.py
│   ├── imports.py
│   ├── search.py
│   ├── settings.py
│   └── system.py
│
├── schemas/
│   ├── song.py
│   ├── movie.py
│   ├── artist.py
│   ├── playlist.py
│   ├── download.py
│   └── ...
│
└── app.py
```

This is only a starting structure and must be validated against the actual V5 codebase.

---

# 10. Download Architecture

The existing download pipeline is one of the most important parts of the application and must be preserved.

Do NOT create a parallel web-only download implementation.

Preferred flow:

```text
React
  ↓
POST /downloads
  ↓
DownloadPlanner
  ↓
DownloadJobManager
  ↓
Provider
  ↓
Filesystem
  ↓
SQLite
```

The browser must not directly invoke providers or download files itself.

The existing download architecture remains authoritative.

---

# 11. Download Jobs

Downloads should be treated as background jobs.

Avoid:

```text
POST /download
      ↓
HTTP request waits several minutes
```

Prefer:

```text
POST /downloads
      ↓
Create job
      ↓
Return job information
      ↓
Background download
      ↓
Progress events
```

Do not introduce Redis/Celery or another distributed queue prematurely.

First reuse the existing DownloadJobManager.

A dedicated distributed queue should only be introduced if actual V6 requirements justify it.

---

# 12. Live Download Progress

V6 should provide live progress using WebSockets or an equivalent event mechanism.

Target flow:

```text
Download worker
      ↓
DownloadProgressEvent
      ↓
WebSocket
      ↓
React
```

UI should show:

- Song title
- Artist
- Source
- Quality
- Status
- Progress
- Speed
- ETA
- Error
- Retry
- Cancellation where supported

No page refresh should be required for progress updates.

---

# 13. Web UI

The initial navigation may contain:

```text
Dashboard
Songs
Movies
Artists
Charts
Playlists
Downloads
Favorites
Search
Settings
Help
```

The exact navigation should be revisited after V5.7.

The UI should remain music-focused without attempting to become a Spotify clone.

Use:

- artwork
- cards
- badges
- quality indicators
- download-state indicators
- rich visual hierarchy
- responsive layouts
- compact information density

Avoid unnecessary visual complexity.

---

# 14. Dashboard

Potential dashboard:

```text
Search
────────────────────────

Downloaded     Not Downloaded
   XXXX             XXX

Recent Downloads
────────────────────────

Recently Added
────────────────────────

Charts / Popular
────────────────────────

Active Downloads
────────────────────────
```

The dashboard should remain compact and useful.

Avoid excessive vertical scrolling.

---

# 15. Songs

The Songs page should support:

- Search
- Filtering
- Sorting
- Pagination / virtualization
- Multi-select
- Download Selected
- Download Missing
- Playback
- Delete/remove
- Open Folder
- Metadata
- Quality
- Source information
- Download status

Use the V5 FTS5/search architecture as the backend foundation.

---

# 16. Movies

Movie pages should preserve V5 movie functionality.

Example:

```text
Movie artwork

Movie title
Year

X songs
X downloaded

[Download All]
[Download Missing]

Track list
```

Movie/song relationships remain many-to-many through the existing normalized relationship model.

Do not introduce `songs.movie_id` merely for the web migration.

---

# 17. People

V6 should preserve the V5 people model:

```text
Artists
├── Singers
├── Music Directors / Composers
└── Actors
```

Person detail pages should expose relevant:

- Songs
- Movies
- Charts
- Playlists
- Relationships

Reuse the normalized V5 artist/person architecture.

Do not create duplicate tables for singers, composers and actors unless the final V5 architecture review proves a genuine need.

---

# 18. Charts

Charts should support:

- Ranking
- Artwork
- Song
- Artist
- Movie
- Download state
- Download Missing
- Source/date metadata where available

The chart implementation from V5 should be reused through the API.

---

# 19. Playlists

Playlists should support:

- Create
- Rename
- Delete
- Add/remove songs
- Reordering
- Playback
- Favorites/ratings where applicable
- Download Missing
- Download Selected

Import flow:

```text
Spotify URL
YouTube URL
Direct playlist URL
       ↓
Analyze
       ↓
Resolve
       ↓
Canonicalize
       ↓
Deduplicate
       ↓
Download
```

The user should not be forced into a manual review workflow for ordinary imports.

The application should internally resolve and deduplicate whenever possible.

---

# 20. Global Search

V6 should provide global search across:

- Songs
- Movies
- Artists
- Playlists
- Charts

Example:

```text
Search: Anirudh

Songs       XXX
Movies       XX
Artists       X
Playlists     X
```

Search should navigate directly to the relevant entity.

Reuse the V5 FTS5/search foundation.

---

# 21. Playback

The browser should be able to stream/play local library audio through controlled API endpoints.

Conceptual flow:

```text
Browser
   ↓
GET /api/songs/{id}/audio
   ↓
Backend
   ↓
Authoritative audio file
```

Do not expose arbitrary filesystem paths to the browser.

---

# 22. Filesystem / Storage

V6 must introduce a clean storage abstraction.

Conceptual structure:

```text
Music Storage
├── library files
├── temporary files
├── artwork cache
└── logs
```

The backend owns filesystem access.

The frontend should not depend on Windows-specific absolute paths.

This is critical for future LAN/cloud deployment.

---

# 23. External Providers

Preserve the V5 provider architecture.

Potential provider types:

```text
HTTP provider
API provider
Direct provider
Browser automation provider
```

Use the least fragile suitable mechanism:

```text
Stable API
   >
Stable HTTP
   >
Browser automation
```

where technically appropriate and permitted.

Do not make Playwright/browser automation mandatory for every source.

Provider failures must be isolated and must not crash the application.

---

# 24. Settings

Potential settings:

### Downloads

- Download directory
- Maximum simultaneous downloads
- Default quality
- Upgrade existing files
- Never downgrade

### Sources

- Enabled providers
- Provider priority
- Source preferences

### Appearance

- Theme
- Compact/comfortable mode

### Playback

- Player behavior

### Advanced

- Developer diagnostics

User-facing UI should avoid engineering terminology.

---

# 25. Developer Diagnostics

Normal users should not be exposed to terms such as:

- SQLite migration
- FTS5
- canonical hash
- provider registry
- internal job IDs
- raw HTTP errors

Developer diagnostics can live under:

```text
Settings
└── Advanced
    └── Developer Diagnostics
```

---

# 26. Authentication

Do not over-engineer authentication before requirements are known.

V6.0 may initially be:

```text
Local/private web application
```

If the final product requires multi-user or internet-hosted operation, introduce:

```text
User
 ↓
Authentication
 ↓
Authorization
 ↓
Library
```

The architecture should avoid making future authentication impossible.

The final authentication decision belongs to the V6 architecture review.

---

# 27. Deployment Strategy

Use incremental deployment targets.

## V6.0

Local:

```text
localhost
```

## V6.1

LAN:

```text
192.168.x.x
```

Allow access from:

- PC
- Laptop
- Phone
- Other trusted LAN devices

## Later

Optional hosted/cloud deployment.

Do not commit to Replit, Docker, VPS, cloud provider, etc. before the architecture review.

Replit may be used later as a development/deployment platform, but it must not dictate the application's architecture.

---

# 28. Responsive Design

V6 should support:

- Desktop
- Laptop
- Tablet
- Mobile browser

Desktop-first is acceptable because this remains a music-library/download-management application.

Expected behavior:

```text
Desktop:
Sidebar + content

Tablet:
Compact sidebar

Mobile:
Navigation drawer / compact navigation
```

---

# 29. Testing Strategy

V6 must preserve the lessons learned during V5.

Tests that only use mocks or fake local downloads are insufficient for release validation.

Use five testing levels.

## Level 1 — Unit

Test:

- Database
- Services
- Providers
- API schemas
- React components
- Utility functions

## Level 2 — Backend Integration

```text
API
 ↓
LibraryService
 ↓
SQLite
```

## Level 3 — Download Integration

```text
API
 ↓
DownloadPlanner
 ↓
DownloadJobManager
 ↓
Real filesystem
```

## Level 4 — Browser E2E

Use a real browser:

```text
Chrome / Chromium
       ↓
React
       ↓
FastAPI
       ↓
SQLite
       ↓
Filesystem
```

## Level 5 — Real-world External Audit

Use a real external source and real workflow:

```text
Real source
    ↓
Real browser
    ↓
Real discovery
    ↓
Real download
    ↓
Real physical file
    ↓
Playback
    ↓
Restart
    ↓
Retry / dedup verification
```

This level is mandatory for source/download changes.

---

# 30. Visual Validation

For each major V6 milestone, capture and inspect real browser screenshots.

At minimum:

- Dashboard
- Songs
- Movie
- Artist
- Charts
- Playlist
- Search
- Downloads
- Settings
- Import flow
- Active download
- Completed download
- Error/retry state

The agent must visually inspect the screenshots.

Do not accept:

> "Screenshot generated successfully."

as sufficient validation.

The agent must check for:

- Clipped text
- Broken layouts
- Missing controls
- Incorrect spacing
- Rendering errors
- Slow/disappearing components
- Mobile/responsive problems
- Incorrect download states

---

# 31. Performance Targets

Initial targets:

- Normal read APIs: ideally <500 ms
- Search: ideally <500 ms
- Simple mutations: ideally <1 second

External provider operations are excluded from these targets because they depend on remote systems and network conditions.

Large lists should use pagination or virtualization.

The frontend must remain responsive during downloads and imports.

---

# 32. V6 Phases

## V6.0 — Architecture & Extraction

Goals:

- Inspect complete V5 architecture
- Identify Tkinter dependencies
- Identify reusable backend services
- Define API boundary
- Define storage strategy
- Define download-job strategy
- Decide authentication direction
- Decide frontend framework
- Decide deployment strategy

**No major UI implementation yet.**

---

## V6.1 — Backend API

Create FastAPI API around existing services.

Initial areas:

- Songs
- Movies
- Artists
- Search
- Downloads
- Imports
- Playlists
- Charts
- Settings

---

## V6.2 — Web Shell

Create React/TypeScript application.

Implement:

- Routing
- Navigation
- Theme
- API client
- Loading states
- Error handling
- Reusable components

---

## V6.3 — Library UI

Implement:

- Dashboard
- Songs
- Movies
- Artists
- Search

---

## V6.4 — Download System

Implement:

- Download Selected
- Download All
- Download Missing
- Retry
- Cancellation where supported
- Queue
- Concurrent downloads
- Live progress
- Speed
- ETA
- Error handling

---

## V6.5 — Import System

Implement:

- Spotify URL
- YouTube URL
- Direct URLs
- Playlist analysis
- Canonical matching
- Deduplication
- Download pipeline

---

## V6.6 — Media Experience

Implement:

- Artwork
- Audio playback
- Player
- Queue
- Playlist playback
- Favorites
- Ratings

---

## V6.7 — Charts / Playlists / Advanced UI

Complete remaining V5 functionality in the web UI.

---

## V6.8 — Real-world Hardening

Perform:

- Real source discovery
- Real browser testing
- Real downloads
- Physical file validation
- Restart testing
- Retry testing
- Duplicate prevention
- Concurrent download testing
- Playback testing
- Filesystem reconciliation

---

## V6.9 — Deployment

Validate:

1. Localhost
2. LAN
3. Optional hosted deployment

---

## V6.10 — V6 Release

Create final V6 release documentation and archive the migration history.

---

# 33. AI Agent Rules for V6

Any AI coding agent working on V6 must follow these rules.

### Rule 1

Never modify `main` directly.

### Rule 2

Work only on the V6 branch or controlled V6 sub-branches.

### Rule 3

Never destroy or overwrite the immutable V5 archive.

### Rule 4

Do not rewrite the download engine without a documented technical reason.

### Rule 5

Do not replace SQLite without explicit approval.

### Rule 6

Do not replace the provider architecture unnecessarily.

### Rule 7

Every significant code change requires automated tests.

### Rule 8

Every UI milestone requires real browser validation.

### Rule 9

Source/download changes require real-world validation.

### Rule 10

Every completed implementation task must:

```text
Inspect
→ Implement
→ Test
→ Run application
→ Visually inspect where applicable
→ Review diff
→ Commit
→ Push
→ Report commit SHA
```

### Rule 11

Do not silently make architectural decisions that contradict this document.

If a requirement conflicts with the plan, stop and explain the conflict before making a large architectural change.

---

# 34. V6 Success Criteria

V6 is successful when the following complete workflow works in a real browser:

```text
Open application
      ↓
Search song
      ↓
Open movie
      ↓
Open artist
      ↓
View chart
      ↓
Import Spotify / YouTube playlist
      ↓
Analyze
      ↓
Resolve
      ↓
Canonicalize
      ↓
Deduplicate
      ↓
Download
      ↓
View live progress
      ↓
Play downloaded song
      ↓
Close browser
      ↓
Restart application
      ↓
Library remains correct
      ↓
Download Missing
      ↓
No duplicate physical files
```

Additionally:

```text
Restart backend
      ↓
Database survives
      ↓
Downloads survive
      ↓
Library survives
      ↓
Job state reconciles
```

---

# 35. Final V5 → V6 Architecture Review

This document is a baseline, not an immutable implementation specification.

At the end of V5.7, perform a formal V6 Architecture Review.

Review:

1. What did V5.4 teach us?
2. What did V5.5 teach us?
3. What did V5.6 teach us?
4. What did V5.7 teach us?
5. Did the database model change?
6. Did provider architecture change?
7. Did download architecture change?
8. Did import architecture change?
9. Are new requirements present?
10. Is authentication required?
11. Is SQLite still appropriate?
12. Should V6 be local, LAN, cloud, or multiple modes?
13. Which frontend framework is most appropriate at that time?
14. Is FastAPI still the best backend boundary?
15. Are browser automation providers required?
16. What V5 functionality must be preserved exactly?
17. What should be redesigned?
18. What should explicitly NOT be carried into V6?

Only after this review should the final V6 implementation plan be approved.

---

# 36. Guiding Principle

The most important rule for V6:

> **Do not rewrite proven functionality simply because the UI is changing.**

The V5 application has already established valuable architecture around:

- Canonical library
- Providers
- Discovery
- Search
- Downloads
- Download planning
- Download jobs
- Deduplication
- Imports
- Filesystem reconciliation
- User metadata
- Playlists
- Charts

V6 should preserve those foundations and expose them through a modern web interface.

The primary transformation is:

```text
                    V5
                     │
                  Tkinter
                     │
                     ▼
              Library Services
                     │
                     ▼
                SQLite/files
```

into:

```text
                    V6
                     │
              React / TypeScript
                     │
                REST/WebSocket
                     │
                  FastAPI
                     │
              Library Services
                     │
                     ▼
                SQLite/files
```

The final architecture must be revalidated at the end of V5.7 before V6 implementation begins.

---

## Status

**V5:** Continue implementation through V5.7.

**V6:** Planning only.

**Do not start V6 implementation until:**

1. All V5.x phases are complete.
2. V5.7 is fully validated.
3. Final V5 archive is created.
4. Final V5 Git tag is created.
5. V6 Architecture Review is completed.
6. This document is revised if required.
7. User explicitly approves V6 implementation.
