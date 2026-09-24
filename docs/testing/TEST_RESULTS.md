# Multi-Tier Test Execution Results

## 1. Execution Overview
- **Date & Time:** 2026-09-16T15:40:00Z
- **Platform:** Windows 11 (Win32)
- **Python Runtime:** Python 3.12.10
- **Test Framework:** pytest 9.1.1 (pluggy 1.6.0)
- **Root Directory:** `C:\Users\Praveen\Downloads\Python Scripts\tamil-mp3-downloader`
- **Total Tests Collected:** 177
- **Total Tests Passed:** 170
- **Total Tests Failed:** 0
- **Total Tests Deselected (Live External):** 7
- **Total Duration:** 227.64 seconds (3 minutes 47 seconds)
- **Status:** **ALL TIERS PASSING (100% SUCCESS)**

---

## 2. Test Breakdown by Tier

| Tier | Directory / File | Collected | Passed | Failed | Deselected / Skipped | Duration | Primary Behaviors Verified |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| **Tier 1: Unit** | `tests/unit/` | 18 | 18 | 0 | 0 | 1.18s | Canonical identity hash, track matching (exact/fuzzy), URL platform detection (Spotify, YouTube, Direct), retry policy with exponential backoff, planner bitrate preference. |
| **Tier 2: Integration** | `tests/integration/` | 5 | 5 | 0 | 0 | 4.72s | Real SQLite database CRUD, physical filesystem integrity, chunked binary HTTP socket streaming, rejection of HTML/Cloudflare masquerade payloads. |
| **Tier 3: Functional** | `tests/functional/` | 10 | 10 | 0 | 0 | 7.89s | Single song download, multi-source failover, provider fallback when all database sources return 404, Spotify embed track & artist extraction, multi-track playlist execution, partial playlist failure handling, physical file deletion & database state reconciliation. |
| **Tier 4: GUI** | `tests/gui/` | 3 | 3 | 0 | 0 | 31.52s | CustomTkinter application startup, view switching, Downloaded Songs interactions (Play/Delete), complete GUI E2E workflow (`test_full_gui_e2e_workflow`). |
| **Tier 5: E2E** | `tests/e2e/` | 1 | 1 | 0 | 0 | 1.60s | End-to-end download pipeline with physical filesystem verification and database invariant check. |
| **Tier 6: Live** | `tests/live/` | 7 | - | - | 7 | - | Opt-in external live provider verification against live MassTamilan, TamilMP3, etc. Deselected by default via `-m "not live"`. |
| **Regression Suite** | `tests/test_*.py` | 133 | 133 | 0 | 0 | 180.73s | Audit fixes, import job persistence, deduplication benchmarks, core library state machines, scraper token extraction, UI architecture. |
| **Total** | **All Tiers** | **177** | **170** | **0** | **7** | **227.64s** | **Complete production functionality verified against real physical filesystem and SQLite state.** |

---

## 3. Verified Production Invariants

1. **Filesystem Ground Truth**:
   - `DownloadRegistry.complete()` only marks records as `OWNED` when the physical file exists and `stat().st_size > 0`.
   - `reconcile_filesystem_integrity()` verifies physical files on application launch, resetting any missing files back to `NEW` with null `file_path`.
2. **Provider Fallback**:
   - When regional scraper sources fail or return 404, `LibraryService.execute_single_download` falls back cleanly to `provider_registry.download_with_fallback` without `NameError`.
3. **Universal URL & Playlist Import**:
   - Modern Spotify embed metadata parses `item['title']` and `item['subtitle']` (artist).
   - Unextractable or empty playlists set job status to `FAILED` with 0 tracks, preventing fake single-track items titled `"Spotify Playlist (<id>)"` by `"Unknown Artist"`.
   - Multi-track execution in `ImportJobManager.execute_job()` writes all files to the authoritative output directory and registers valid rows in `songs`.
4. **Canonical Output Directory**:
   - Consolidated `settings.output_dir` property fallback to `downloads`, eliminating competing directories and dead pytest temporary paths.
