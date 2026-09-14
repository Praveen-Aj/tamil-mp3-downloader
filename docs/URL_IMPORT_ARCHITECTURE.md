# URL & Playlist Import Architecture: Open-Source Research & Design Spec

## 1. Executive Summary

This document synthesizes architectural patterns from leading open-source media acquisition tools—specifically **spotDL**, **yt-dlp**, and **playlistdl**—to establish a robust, modern, and legally sound URL/playlist import workflow for Tamil MP3 Downloader.

The fundamental design shift separates **Platform Metadata Resolution** from **Audio Stream Acquisition**:

$$\text{Platform URL} \xrightarrow{\text{Resolver}} \text{Canonical Metadata} \xrightarrow{\text{Matcher}} \text{Audio Provider Candidates} \xrightarrow{\text{Ranking}} \text{Stream Download} \xrightarrow{\text{Tagger}} \text{Canonical SQLite Library}$$

---

## 2. Research & Open-Source Pattern Extraction

### 2.1 spotDL Architecture Patterns
* **Metadata vs. Audio Decoupling**: Spotify does not serve unprotected MP3 streams. spotDL treats Spotify exclusively as a rich metadata source (fetching title, artist, album, duration, ISRC, release year, and high-res cover art).
* **Search & Fuzzy Matching**: Queries audio providers (YouTube / YouTube Music) using combined metadata terms, then computes a weighted scoring formula:
  * Duration Delta: Penalizes candidates whose duration deviates from metadata by more than $\pm 8\text{ seconds}$.
  * Token Set / Sequence Matching: Normalized string distance between artist/title strings.
  * Channel Reputation / Official Flag: Bonus score if the uploader is an official artist channel or topic channel.
* **Persistent Playlist State (`.spotdl` save files)**: spotDL serializes playlist track statuses (`downloaded`, `failed`, `skipped`) to allow partial resumes without re-downloading existing tracks.
* **Tagging Pipeline**: Direct integration with `mutagen` for ID3v2.3 tagging including cover artwork injection.

### 2.2 yt-dlp Architecture Patterns
* **High-Speed Playlist Enumeration (`extract_flat=True`)**:
  yt-dlp avoids downloading individual format streams during initial inspection. Using `extract_flat`, it enumerates hundreds of playlist entries in seconds, extracting only titles, IDs, and estimated durations.
* **Granular Error Hierarchy**:
  yt-dlp distinguishes `DownloadError`, `GeoRestrictedError`, `UnavailableVideoError`, and `ExtractorError`. Instead of raw Python tracebacks, it allows callers to map errors to user-friendly messages.
* **Stream Quality Filtering**:
  Selecting audio formats (`bestaudio[ext=m4a]/bestaudio/best`) ensures maximum fidelity while falling back gracefully when FFmpeg is not installed.
* **Atomic File Writes**:
  Writes to `.part` files first, verifying file integrity and size before renaming to the final `.mp3` path.

### 2.3 playlistdl Patterns
* **Chunked Batch Processing**: Processing playlist tracks in worker pools with rate-limiting backoffs to avoid platform throttling.
* **Individual Track State Tracking**: Maintains an in-memory or database ledger for each item (`PENDING`, `DOWNLOADING`, `COMPLETED`, `FAILED`, `CANCELLED`).

---

## 3. Comparison: Existing Support vs. New Additions

| Feature Area | Current v4.0.0 Architecture | New Universal URL Import System (v4.1.0) |
| :--- | :--- | :--- |
| **Primary Workflow** | Category-based regional site scraping (MassTamilan, TamilMP3, FriendsTamilMP3) | Universal URL input: Spotify, YouTube, YouTube Music, Regional sites, Direct Audio URLs |
| **Spotify Handling** | Not supported | Full metadata resolution (Track, Album, Playlist) $\to$ candidate audio resolution |
| **Audio Providers** | Hardcoded scrapers tied to regional HTTP downloads | Pluggable `AudioProvider` abstraction (`YouTubeProvider`, `TamilRegionalProvider`, `DirectAudioProvider`) |
| **Matching Logic** | Exact/Normalized title + artist hash | Fuzzy multi-factor match score (Title, Artist, Duration delta, Quality, Reliability) |
| **Match Confidence** | Binary match | Tiered: `HIGH` ($\ge 85\%$), `MEDIUM` ($65-84\%$), `LOW` ($< 65\%$), `NO MATCH` |
| **Playlist Jobs** | Ephemeral batch execution | Persistent, resumable SQLite jobs (`import_jobs`, `import_job_items`) surviving restarts |
| **Failure Recovery** | Manual retry of failed downloads | Resumable playlist sessions; "Retry Failed Tracks Only" |
| **Local File Import** | Primary "Import" tab | Repositioned under `Library → Import Existing Files` as secondary workflow |
| **Error Feedback** | Basic log messages | Human-actionable reason codes and suggested actions (no raw tracebacks) |

---

## 4. Dependencies & Platform Limitations

### Dependencies
1. **`yt-dlp`**: Added to `requirements.txt`. Used for YouTube / YouTube Music search and stream resolution.
2. **`mutagen`**: Already installed. Used for ID3 tagging (Title, Artist, Album, Year, Track Number, Artwork).
3. **`requests` / `cloudscraper`**: Already installed. Used for Spotify oEmbed / embed metadata scraping and direct HTTP downloads.
4. **`FFmpeg` (External System Tool)**:
   * *Status*: Optional external binary.
   * *Graceful Fallback*: If FFmpeg is absent, the system fetches native stream formats (such as `.m4a` or native audio streams) and tags them directly without throwing execution errors. A clear alert in Settings/Help informs the user how to install FFmpeg if format conversion is desired.

### Platform Limitations
* **Spotify DRM**: Spotify audio is encrypted with DRM. We **do not** bypass DRM or access private Spotify streams. Instead, we query alternative public audio providers using metadata matches.
* **YouTube Rate Limits**: Rapid concurrent requests can trigger temporary 429 throttling. The provider incorporates jittered backoff and configurable worker limits.
* **Private / Geoblocked Playlists**: Playlists requiring platform login or georestricted tracks are flagged as `AUTH REQUIRED` or `UNAVAILABLE` without breaking the rest of the batch.
