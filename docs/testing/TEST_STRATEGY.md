# Test Strategy & Architecture Specification

## 1. Overview
This document specifies the multi-tier test architecture for the **Tamil MP3 Downloader** desktop application.
The primary purpose of this testing architecture is to guarantee that the application's core functionality (music acquisition, file downloading, ID3 tagging, filesystem truth, and UI responsiveness) is continuously and reliably validated without relying on tautological mocks or unverified database flags.

---

## 2. Core Invariants (Ground Truth)

A song or download is subject to strict physical filesystem invariants:
1. **Download Completion Invariant**:
   - A download is marked `COMPLETED` if and only if:
     - The physical file exists on disk.
     - The file is a regular file (`is_file() == True`).
     - The file size is strictly greater than 0 (`stat().st_size > 0`).
     - The binary header matches valid audio signatures (rejecting HTML error/Cloudflare pages).
     - No `.part` or `.tmp` file remains.
2. **Database Ownership Invariant**:
   - A song in SQLite table `songs` has `state = 'OWNED'` if and only if:
     - `file_path` is non-null and non-empty.
     - `Path(file_path).exists() == True`.
     - `Path(file_path).stat().st_size > 0`.
3. **Reconciliation Invariant**:
   - If an `OWNED` song's physical file is removed or missing from disk, `reconcile_filesystem_integrity()` resets its state back to `NEW` with `file_path = NULL`.
   - The UI and dashboard statistics never fabricate disk storage values; storage calculations must be derived from verified physical files.
4. **Authoritative Directory Invariant**:
   - All normal downloads and URL/playlist imports must write to the single configured directory defined by `settings.output_dir` (defaulting to the canonical project `downloads/` directory). Competing directory fallbacks (such as `"output"`) are prohibited.

---

## 3. Test Tier Breakdown

| Tier | Directory | Scope & Purpose | Mock vs Real Boundaries | Execution Rule |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Unit** | `tests/unit/` | Pure logic, regexes, canonical hashing, string normalization, track matching, retry policies, planner decisions. | **100% In-Memory / Isolated**: No network, no persistent disk. | Fast, runs on every commit. |
| **Tier 2: Integration** | `tests/integration/` | Database persistence, binary header validation, chunked HTTP socket streaming. | **Real SQLite, Real Filesystem (`tmp_path`), Real Local HTTP Socket Server**. | Deterministic socket testing without external web dependencies. |
| **Tier 3: Functional** | `tests/functional/` | Multi-step workflows: single song download with source failover, playlist import execution with multi-track registration, partial failure handling, deletion & file unlinking. | **Real Services & Subsystems**: `LibraryService`, `ImportJobManager`, `ProviderRegistry`, `DownloadRegistry`. | Uses local deterministic audio socket server. |
| **Tier 4: GUI** | `tests/gui/` | CustomTkinter views and event lifecycles: Add Music, Downloads Manager, Downloaded Songs, Dashboard metrics. | **Real CustomTkinter UI Instances**: Interacts with widgets, triggers callbacks, checks UI state against filesystem truth. | Headless/desktop compatible. Reuses Tk context safely. |
| **Tier 5: E2E** | `tests/gui/test_gui_e2e_workflow.py` & `tests/e2e/` | Complete user journey: Launch app -> Add Music -> Analyze URL -> Download -> Verify physical file -> Navigate to Downloaded Songs -> Play/Open Folder -> Delete -> Verify unlinked file. | **Full Stack**: Exercises entire production path end-to-end. | Deterministic local server fixture. |
| **Tier 6: Live** | `tests/live/` | External verification against live web sources (YouTube, Spotify public endpoints, regional scrapers). | **Real Internet**: Requires live internet access and external site availability. | Marked with `@pytest.mark.live`. Skipped by default in CI/standard runs. |

---

## 4. Shared Test Fixtures (`tests/conftest.py` & `tests/fixtures_helper.py`)

- `valid_mp3_bytes`: Deterministic binary byte generator producing valid MPEG-1 Layer 3 audio frames with ID3v2 metadata header.
- `local_audio_server` / `http_server`: High-performance Python socket server bound to `127.0.0.1:0` serving:
  - `/valid-song.mp3`, `/track1.mp3`, `/track2.mp3` (HTTP 200 with audio/mpeg headers).
  - `/not-found.mp3` (HTTP 404).
  - `/html-masquerade.mp3` (HTTP 200 with text/html body simulating Cloudflare/anti-bot blocks).
  - `/empty.mp3` (HTTP 200 with 0 bytes).
  - `/flaky-song.mp3` (HTTP 503 twice, then HTTP 200 on 3rd attempt for retry testing).
- `test_db`: Fresh isolated SQLite database with full schema migrations in `tmp_path`.
- `temp_downloads_dir`: Isolated output directory in `tmp_path`.

---

## 5. Acceptance Criteria Checklist

- [ ] All normal single-song downloads execute through to verified physical files on disk.
- [ ] Provider fallback for normal downloads executes cleanly without `NameError`.
- [ ] Spotify playlist analysis parses modern embed JSON (`__NEXT_DATA__` `trackList` with `title`, `subtitle` as artist, duration).
- [ ] Empty or failed playlist URLs do not generate fake single-song download items with `"Unknown Artist"`.
- [ ] Multi-track playlist import downloads all selected tracks and registers each in SQLite.
- [ ] Partial playlist failures report accurate completed vs failed metrics without creating fake `OWNED` records.
- [ ] Filesystem reconciliation clears orphaned database records on application launch.
- [ ] All test tiers pass cleanly under `pytest`.
