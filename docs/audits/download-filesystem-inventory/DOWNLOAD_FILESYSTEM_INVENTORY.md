# Download Filesystem Inventory & Audio Audit

**Date**: 2026-10-02  
**Branch**: `feature/v6-web-migration`  
**Authoritative Download Directory**: `C:\Users\Praveen\Downloads\Songs New`  
**Status**: READ-ONLY AUDIT COMPLETED. NO FILES WERE DELETED OR MOVED.

---

## 1. Executive Summary

| Category | Description | File Count | Total Size (Bytes) | Total Size (MB) |
|---|---|---:|---:|---:|
| **CURRENT_LIBRARY_FILE** | Physical audio files referenced by active SQLite DB (`state=OWNED`) | 3 | 16,484,075 | 15.72 MB |
| **CURRENT_DOWNLOAD_DIR_UNTRACKED** | Audio files in authoritative `Songs New` not tracked in DB | 0 | 0 | 0.00 MB |
| **LEGACY_APPLICATION_FILE** | Historical downloads in `C:\Users\Praveen\Downloads\Songs` | 824 | 7,378,179,970 | 7,036.38 MB |
| **TEST_ARTIFACT** | Temporary visual mock files in `tmp_visual_validation` | 3 | 24,588 | 0.02 MB |
| **V5_BACKUP_OR_ARCHIVE** | Audio preserved in `data/audit_v5_6/` (+ 121 in `v5_final_full_project_backup.zip`) | 4 | 28,376,217 | 27.06 MB |
| **UNKNOWN** | Unidentified loose audio files | 0 | 0 | 0.00 MB |
| **TOTAL DISCOVERED AUDIO** | **All physical audio files on disk** | **834** | **7,423,064,850** | **7,079.18 MB (7.08 GB)** |

---

## 2. Authoritative Directory (`C:\Users\Praveen\Downloads\Songs New`)

- **Total Files**: 3 (2 audio files + 1 JSON metadata sidecar)
- **Total Audio Files**: 2
- **Total Physical Size**: 11,193,330 bytes (10.67 MB)
- **Audio Size**: 11,192,874 bytes (10.67 MB)
- **Format Breakdown**:
  - `.mp3`: 1 file (`Track - Kalla Nikkiriye.mp3`, 9,697,206 bytes, 320 kbps CBR, 48 kHz stereo)
  - `.webm`: 1 file (`Track - Anbil Avan - Title Theme.webm`, 1,495,668 bytes, ~133.45 kbps Opus)
  - `.json`: 1 sidecar (`Anbil Avan\.download_state.json`, 456 bytes)
- **Untracked Audio Files**: **0** (all audio files in `Songs New` are tracked by the current library database).

---

## 3. Database Cross-Check

**Active Database**: `C:\Users\Praveen\AppData\Roaming\tamil-mp3-downloader\library.db`  
**Total Tracks in Catalog**: 855 songs (821 `NEW`, 31 `FAILED`, 3 `OWNED`)

| Metric | Count | Details |
|---|---:|---|
| **DB says OWNED + physical file exists** | **3** | • ID 3: *Anbil Avan - Title Theme* (`Track - Anbil Avan - Title Theme.webm`)<br>• ID 5: *Aasai Varame* (`downloads\Track - Aasai Varame.mp3`)<br>• ID 7: *Kalla Nikkiriye* (`Track - Kalla Nikkiriye.mp3`) |
| **DB says OWNED + physical file missing** | **0** | All 3 `OWNED` tracks exist physically on disk at their recorded paths. |
| **File exists in `Songs New` + DB untracked** | **0** | No rogue audio files in authoritative folder. |
| **File exists outside + DB untracked** | **831** | Legacy collection (824), V5 test audit (4), visual test mocks (3). |

---

## 4. Special Attention: `downloads\Track - Aasai Varame.mp3`

- **Absolute Path**: `C:\Users\Praveen\Downloads\Python Scripts\tamil-mp3-downloader\downloads\Track - Aasai Varame.mp3`
- **File Size**: 5,291,201 bytes (~5.05 MB)
- **SHA-256**: `b0089c6b9ede122c7e127f021e07873a5499b66f3fb1fecac1efbf936ec1058b`
- **Format & Codec**: MPEG-1 Layer 3 (MP3), 320,000 bps (320 kbps CBR), 48,000 Hz, stereo
- **Belongs to Current DB?**: **YES**. Song ID 5 in `library.db` records this exact path with `state = 'OWNED'`.
- **Does another copy exist in `Songs New`?**: **NO**.
- **Root Cause**: Created during previous test suite execution when `test_api_settings_crud` temporarily configured `download_dir = "downloads"`.
- **Recommendation**: DO NOT delete. In a future controlled migration task, relocate this file to `C:\Users\Praveen\Downloads\Songs New\Track - Aasai Varame.mp3` and update the SQLite row for Song ID 5.

---

## 5. Duplicate File Analysis

### A. Byte-for-Byte Identical Files (Identical SHA-256)
- **Group 1**: Hash `01b178ceb90390fac6ceb041cf5e1bf5c8d6ceb808945625bf9652a970da6b83` (3 files, 8,196 bytes each)
  - `tmp_visual_validation\downloads\Arabic Kuthu - Anirudh Ravichander.mp3`
  - `tmp_visual_validation\downloads\Matta - Yuvan Shankar Raja.mp3`
  - `tmp_visual_validation\downloads\Vaathi Coming - Anirudh.mp3`
  - *Analysis*: Identical dummy test fixtures generated during UI styling tests.

### B. Same-Song Normalized Title Groups (9 Groups in Legacy Collection)
All 9 groups reside in the legacy `C:\Users\Praveen\Downloads\Songs` folder:
1. `Danga Maari Oodhari`: Movie album version (14.18 MB, 320 kbps) vs Singer Hits version (12.80 MB, 296 kbps VBR).
2. `Nila Nila Poguthae`: Full track (13.50 MB, 320 kbps) vs Bit version (2.65 MB, 320 kbps).
3. `Undhan Mugam`: Original (7.51 MB, 320 kbps) vs Composer Version (9.27 MB, 320 kbps).
4. `Vaayamoodi Summa Iru Da`: Guitar version (11.46 MB, 320 kbps) vs Strings version (11.40 MB, 320 kbps).
5. `Ennama Kannu`: Rajini Hits 2 version (4.51 MB, 128 kbps) vs Singer Hits version (3.95 MB, 128 kbps).
6. `Yennamma Ippadi Panreengalaema`: Original (11.18 MB, 320 kbps) vs Club Mix (11.14 MB, 320 kbps).
7. `Vaada Vaada`: Original (11.29 MB, 320 kbps) vs Singer Hits version (9.66 MB, 237 kbps VBR).
8. `Poove Poove`: Original (11.33 MB, 320 kbps) vs Remix (11.03 MB, 320 kbps).
9. `MothaThabaa Parthen`: Original (12.22 MB, 320 kbps) vs Remix (8.10 MB, 320 kbps).

---

## 6. Legacy & Archive Locations

### Location 1: `C:\Users\Praveen\Downloads\Songs` (Legacy User Collection)
- **Status**: Legacy application storage from previous versions.
- **Audio Files**: 824 MP3 files across 95 album/movie subdirectories.
- **Total Size**: 7,378,179,970 bytes (~7.04 GB).
- **Safety**: **DO NOT DELETE**. This is the user's historical music library.

### Location 2: `data\audit_v5_6\music\` (V5 Integration Test Data)
- **Status**: V5 preservation artifacts.
- **Audio Files**: 4 MP3 files (Baththa and User Request OST).
- **Total Size**: 28,376,217 bytes (27.06 MB).
- **Safety**: **DO NOT DELETE**. Preserved as part of V5 verification history.

### Location 3: `backup\v5_final_full_project_backup.zip` (Sacred V5 Archive)
- **Status**: Sacred project archive.
- **Audio Files Packed**: 121 MP3 files inside zip.
- **Total Archive Size**: 521,933,285 bytes (~522 MB).
- **Safety**: **SACRED. NEVER MODIFY OR DELETE.**

---

## 7. Recommended Cleanup Candidates (For Future Controlled Phase)

| Candidate File / Group | Location | Size | Classification | Rationale |
|---|---|---:|---|---|
| `tmp_visual_validation\downloads\*.mp3` (3 files) | `tmp_visual_validation\` | 24.588 KB | `TEST_ARTIFACT` | Dummy mock files (8KB each, identical SHA-256) created for visual layout testing. Safe to clean up in a dedicated maintenance pass. |
| `Track - Anbil Avan - Title Theme.webm` | `Songs New\` | 1.496 MB | `CURRENT_LIBRARY_FILE` (Transitional) | WebM Opus fallback. Once replaced/upgraded by the new 320 kbps MP3 pipeline, the obsolete WebM container can be safely retired. |
| `downloads\Track - Aasai Varame.mp3` | `downloads\` | 5.291 MB | `CURRENT_LIBRARY_FILE` (Misplaced) | Legitimate 320 kbps track recorded in DB ID 5. Relocate to `Songs New` and update DB record; do not delete. |

*Note: No files were deleted or moved during this audit.*
