# V6 UI/UX Redesign — Current State Screenshots

**Purpose:** Visual evidence of the current rendered frontend before any redesign changes are applied.
These screenshots represent the *baseline* state of the V6 web migration on branch `feature/v6-web-migration`.

---

## Capture Metadata

| Field | Value |
|---|---|
| **Branch** | `feature/v6-web-migration` |
| **Rendered Commit (HEAD SHA)** | `81650c57869f38ed666f923f9ec0bacb5e4a8b50` |
| **Application URL** | `http://127.0.0.1:8765` |
| **Backend** | FastAPI (`api/app.py`) via uvicorn |
| **Frontend** | Vite production build (`web/dist/`) served by FastAPI static handler |
| **Screenshot Tool** | Playwright headless Chromium (via Python `playwright` async API) |
| **Capture Date** | 2026-09-28 |
| **Screenshots from actual running app** | **YES** — captured from live `http://127.0.0.1:8765` |

---

## Desktop Screenshots — 1536 x 730 px

| # | Page | Filename | Size |
|---|---|---|---|
| 01 | Dashboard (Home) | `desktop-01-dashboard.png` | 669 KB |
| 02 | Songs Library | `desktop-02-songs.png` | 203 KB |
| 03 | Movies & Soundtracks | `desktop-03-movies.png` | 745 KB |
| 04 | Artists | `desktop-04-artists.png` | 249 KB |
| 05 | Search (query: "AR Rahman") | `desktop-05-search.png` | 679 KB |
| 06 | Favorites | `desktop-06-favorites.png` | 81 KB |
| 07 | Playlists | `desktop-07-playlists.png` | 55 KB |
| 08 | Downloads Manager | `desktop-08-downloads.png` | 142 KB |
| 09 | Import | `desktop-09-import.png` | 73 KB |
| 10 | Settings | `desktop-10-settings.png` | 108 KB |
| 11 | Sidebar Navigation (from Dashboard) | `desktop-11-sidebar-nav.png` | 669 KB |
| 12 | Top Charts | `desktop-12-charts.png` | 63 KB |
| 13 | Player Active (song playing from Songs view) | `desktop-13-player-active.png` | 203 KB |

---

## Mobile Screenshots — 390 x 844 px (iPhone-class, 2x device pixel ratio)

| # | Page | Filename | Size |
|---|---|---|---|
| 14 | Dashboard (Home) | `mobile-01-dashboard.png` | 372 KB |
| 15 | Player + Bottom Nav visible | `mobile-02-player-nav.png` | 609 KB |
| 16 | Songs (Library tab in bottom nav) | `mobile-03-songs.png` | 206 KB |

---

## Total Files

**16 screenshots** — 13 desktop + 3 mobile.

---

## Verification

- All screenshots were captured by running the Playwright headless browser against the **actual live application** at `http://127.0.0.1:8765`.
- The frontend was built from the current commit using `npm run build` in `web/`.
- The backend was started using `.venv/Scripts/python.exe -m uvicorn api.app:app --host 127.0.0.1 --port 8765`.
- **No design changes were made** to produce these screenshots. This is the exact unmodified current state.

---

## Design Notes (Baseline Audit — For Reference Only)

These screenshots document the **current navy/indigo-blue aesthetic** (`#080c14` backgrounds, `#6366f1` + `#06b6d4` dual-accent) that is targeted for redesign. No changes have been applied at this commit.
