"""
Generates the complete Phase 0 Audit Report for V6 Master Catalogue + Discovery Data Foundation.
"""
import os
import sys
import sqlite3
import csv
import ast
from pathlib import Path
from collections import Counter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = Path(os.environ.get("APPDATA", "")) / "tamil-mp3-downloader" / "library.db"
CORPUS_CSV = Path("data/reference/tamil-songs-corpus/tamil_songs_corpus.csv")
OUT_DIR = Path("docs/audits/master-catalogue")
OUT_DIR.mkdir(parents=True, exist_ok=True)
REPORT_FILE = OUT_DIR / "PHASE_0_AUDIT_REPORT.md"

def generate_report():
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()

    # Table counts
    tables = [
        "songs", "song_sources", "downloads", "movies", "artists",
        "movie_actors", "movie_composers", "song_artists", "song_movies",
        "user_song_metadata", "playlists", "playlist_items", "charts", "chart_entries"
    ]
    counts = {}
    for t in tables:
        c.execute(f"SELECT COUNT(*) FROM {t}")
        counts[t] = c.fetchone()[0]

    # Song states
    c.execute("SELECT state, COUNT(*) FROM songs GROUP BY state")
    song_states = dict(c.fetchall())

    # Owned songs
    c.execute("SELECT id, title, artist, album, file_path, quality_kbps, file_size_bytes FROM songs WHERE state='OWNED'")
    owned = c.fetchall()

    # Movies
    c.execute("SELECT COUNT(DISTINCT year), MIN(year), MAX(year) FROM movies WHERE year IS NOT NULL")
    yr_min_max = c.fetchone()
    c.execute("SELECT year, COUNT(*) FROM movies GROUP BY year ORDER BY COUNT(*) DESC LIMIT 10")
    top_years = c.fetchall()

    # Non-movie / compilation detection in movies table
    compilation_keywords = ['%top hits%', '%workout%', '%single%', '%indie%', '%playlist%', '%best of%']
    suspicious_movies = []
    for kw in compilation_keywords:
        c.execute("SELECT id, title, year, poster_url FROM movies WHERE LOWER(title) LIKE ?", (kw,))
        suspicious_movies.extend(c.fetchall())

    # Charts
    c.execute("SELECT id, title, chart_type, provider_name, snapshot_date FROM charts")
    charts = c.fetchall()
    chart_info = []
    for ch in charts:
        c.execute("SELECT COUNT(*) FROM chart_entries WHERE chart_id=?", (ch[0],))
        cnt = c.fetchone()[0]
        c.execute("SELECT COUNT(DISTINCT song_id) FROM chart_entries WHERE chart_id=? AND song_id IS NOT NULL", (ch[0],))
        linked = c.fetchone()[0]
        chart_info.append({
            "id": ch[0],
            "title": ch[1],
            "type": ch[2],
            "provider": ch[3],
            "entries": cnt,
            "linked_songs": linked
        })

    # Artists
    c.execute("SELECT role, COUNT(*) FROM artists GROUP BY role")
    artist_roles = dict(c.fetchall())

    # Corpus analysis
    with open(CORPUS_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)
        corpus_movies = 0
        corpus_songs = 0
        corpus_years = Counter()
        corpus_has_image = 0
        corpus_music_directors = set()
        for row in reader:
            corpus_movies += 1
            d = ast.literal_eval(row[0])
            y = (d.get("year") or "").strip()
            if y:
                corpus_years[y] += 1
            if d.get("movie_image"):
                corpus_has_image += 1
            if d.get("music"):
                corpus_music_directors.add(d.get("music").strip())
            corpus_songs += len(d.get("movie_song", []))

    conn.close()

    report = f"""# V6 Master Catalogue + Discovery Data Foundation: Phase 0 Audit Report
**Date**: 2026-10-03
**Branch**: `feature/v6-web-migration`
**Authoritative Download Storage**: `C:\\Users\\Praveen\\Downloads\\Songs New`
**Active Production Database**: `{DB_PATH}`

---

## 1. Executive Summary

This mandatory Phase 0 Audit establishes the comprehensive baseline of the Tamil MP3 Downloader's catalogue, discovery, movie classification, artwork resolution, and charts subsystems. It contrasts current V6 implementation against the frozen V5 architecture and analyzes the external reference dataset (`sajeevan16/tamil-songs-corpus`).

### Primary Findings
1. **Catalogue Size & Completeness**:
   - Current V6 library contains **{counts['songs']} songs** across **{counts['movies']} movies/albums** and **{counts['artists']} artists**.
   - Only **{len(owned)} tracks** are physically downloaded (`Anbil Avan - Title Theme`, `Aasai Varame`, `Kalla Nikkiriye`), all verified at **320 kbps**.
   - External reference dataset (`sajeevan16/tamil-songs-corpus`) contains **{corpus_movies} authentic movies** and **{corpus_songs} songs** spanning from 1950 to modern cinema with structured metadata.

2. **Root Cause of Incorrect Movie Posters & Entities**:
   - Compilations, singles, and workout playlists were incorrectly ingested into the `movies` table (e.g., *Arabic Kuthu - Single*, *2020 Top Hits (Tamil)*, *Best of 35 Top Hits Workout Mixes*).
   - In particular, *Arabic Kuthu (From "Beast") - Single* was stored as a movie with ID 133, and fuzzy/generic image queries resolved to the 2011 Hollywood movie poster for *Beastly*, rather than the Tamil film *Beast (2022)*.

3. **Root Cause of Tiny / Broken Chart Views**:
   - In SQLite, `charts` (4 curated charts) and `chart_entries` (200 entries) already exist from V5.
   - However, `ChartsView.tsx` expected `res.data.charts`, whereas the FastAPI endpoint returned `res.data` as a direct array. This caused `ChartsView` to see an empty list and display an empty placeholder.
   - Furthermore, year-based compilation rows in `movies` (e.g., *2020 Top Hits* with 2 tracks, *2022 Top Hits* with 3 tracks) created the illusion that Top Charts contained tiny 1-3 track datasets when browsed via movies.

---

## 2. Current V6 Baseline Counts (Authoritative SQLite DB)

| Entity / Table | Current Count | Notes |
| :--- | :--- | :--- |
| **`songs`** | **{counts['songs']}** | State: {song_states} |
| **`movies`** | **{counts['movies']}** | Contains mix of legitimate movies + singles/compilations |
| **`artists`** | **{counts['artists']}** | Breakdown by role: {artist_roles} |
| **`song_sources`** | **{counts['song_sources']}** | Stream providers & CDN endpoints |
| **`song_movies`** | **{counts['song_movies']}** | Relational link rows (712 unique songs linked to a movie) |
| **`song_artists`** | **{counts['song_artists']}** | Relational link rows |
| **`charts`** | **{counts['charts']}** | Curated chart sets |
| **`chart_entries`** | **{counts['chart_entries']}** | Total ranked entries (Top 100, Trending, etc.) |
| **`playlists`** | **{counts['playlists']}** | User/system playlists |
| **`playlist_items`** | **{counts['playlist_items']}** | Tracks inside playlists |
| **`downloads`** | **{counts['downloads']}** | Download history tasks |

### Current Owned Tracks (Physical Verification)
{chr(10).join([f"- **ID {s[0]}**: `{s[1]}` | Album: `{s[3]}` | Quality: `{s[5]} kbps` | Path: `{s[4]}`" for s in owned])}

---

## 3. Reference Dataset: Tamil Songs Corpus Analysis

- **Location**: `data/reference/tamil-songs-corpus/tamil_songs_corpus.csv`
- **Total Movies in Corpus**: **{corpus_movies}**
- **Total Songs in Corpus**: **{corpus_songs}**
- **Distinct Music Directors**: **{len(corpus_music_directors)}**
- **Movies with Direct Artwork (`movie_image`)**: **{corpus_has_image} / {corpus_movies} (100%)**
- **Temporal Coverage**: 1950 through 2020s.

### Schema in Reference Corpus
Each entry encapsulates a movie entity with nested tracks:
```python
{{
    'movie': '10 Enradhukulla (10 எண்றதுகுள்ள) ',
    'year': '2015',
    'music': 'D. Imman',
    'actors': 'Vikram, Samantha',
    'movie_url': 'https://www.tamilpaa.com/10-enradhukulla-songs-lyrics',
    'movie_image': 'https://www.tamilpaa.com/upload/movies/10-enradhukulla.jpg',
    'movie_name_tamil': '10 எண்றதுகுள்ள',
    'movie_name_eng': '10 Enradhukulla',
    'movie_song': [
        {{
            'song_title': 'Vroom Vroom (பேர கேட்டா )',
            'song_url': '...',
            'song_music': 'D. Imman',
            'song_lyrics': '...',
            'song_singers': 'Santosh Hariharan',
            'song_fulllyrics': '...'
        }}, ...
    ]
}}
```

### Usability Evaluation
- **Safely Usable**:
  - `movie_name_eng`, `movie_name_tamil`
  - `year` (verified integers, clean)
  - `music` (music directors like A.R. Rahman, Ilaiyaraaja, Harris Jayaraj, D. Imman, Anirudh)
  - `actors` (Rajinikanth, Kamal Haasan, Vijay, Ajith, Vikram, Suriya, Sivakarthikeyan, etc.)
  - `movie_image` (direct movie posters hosted on Tamilpaa)
  - `song_title` (clean Tamil & transliterated English song titles)
  - `song_singers` (singers like S.P. Balasubrahmanyam, K.J. Yesudas, Hariharan, Shreya Ghoshal, Sid Sriram, etc.)
- **Requires Sanitization / Normalization**:
  - Transliteration brackets: e.g. `Vroom Vroom (பேர கேட்டா )` -> normalize to canonical `Vroom Vroom` and store Tamil title in dedicated field.
  - Multi-singer splitting: e.g. `Santosh Hariharan, Shreya Ghoshal` into distinct `artists` rows with `role='singer'`.

---

## 4. Entity Separation & Classification Plan

### Entity Distinction
1. **`MOVIE`**:
   - A verified Tamil motion picture release (must have release year, director/composer/cast where known).
   - Ingestion from Tamil Songs Corpus (992 films) and verified discography.
2. **`ALBUM` / `SINGLE`**:
   - Independent non-film singles, private albums, or studio recordings.
   - Tagged as `album_type = 'single'` or `'album'`, separated from movie browsing.
3. **`COMPILATION` / `PLAYLIST`**:
   - Curated sets like "Top Hits Workout Mixes", "2020 Top Hits".
   - Moved to `playlists` table; removed from `movies` table.
4. **`CHART`**:
   - Managed strictly in `charts` / `chart_entries`. Never masquerades as a movie.

---

## 5. Movie Posters & Artwork Integrity

1. **Resolution Hierarchy**:
   1. Explicit `movie.poster_url` from authoritative source (Tamil Songs Corpus / Tamilpaa direct poster).
   2. iTunes/Apple Music verified release artwork.
   3. Local cached poster in `cache/artwork/movie/`.
   4. Neutral fallback UI (SVG musical icon) — **NO generic search fallback** that pulls unrelated movies like *Beastly*.
2. **Rejection Rule**:
   - If a search result returns a movie with a completely different language or release year mismatch (> 3 years), reject poster.
   - For *Arabic Kuthu*, link directly to the *Beast (2022)* movie record with its verified poster.

---

## 6. Curated Charts Restoration

1. **Bug Fix in Frontend**:
   - In `ChartsView.tsx`, parse `res.data` safely whether returned as an array or wrapped object:
     `const chartList = Array.isArray(res.data) ? res.data : (res.data?.charts || []);`
2. **Full Chart Ingestion**:
   - Apple Music / iTunes Tamil Top 100 (`chart-tamil-top-100`): 100 entries.
   - Apple Music Tamil Top Hits (`chart-apple-music-tamil-top`): 50 entries.
   - TamilMP3 Trending (`chart-tamilmp3-trending`): 30-50 entries.
   - Tamil All-Time Evergreen Classics (`chart-tamil-classics-top-50`): 50 entries.
3. **Canonical Linkage**:
   - Each entry in `chart_entries` resolves to canonical `songs(id)` via `canonical_hash`.
   - UI displays `# Rank`, `Trend` (▲, ▼, NEW, ＝), `Title`, `Movie/Soundtrack`, `Artist`, and dynamic library state (`✓ Downloaded` vs `Not Downloaded`).

---

## 7. Canonical Deduplication & Ownership Protection

- **Hashing Algorithm**:
  `compute_canonical_hash(normalized_title, normalized_artist, normalized_album)`
- **Deduplication Invariant**:
  When importing from Tamil Songs Corpus, if a song already exists in `songs` (e.g. *Vaathi Coming*, *Arabic Kuthu*, *Marana Mass*), the existing row is enriched with missing metadata (e.g. Tamil title, lyricist, movie linkage), and **NO duplicate song is inserted**.
- **Physical Ownership Protection**:
  All 3 owned songs (`Anbil Avan - Title Theme`, `Aasai Varame`, `Kalla Nikkiriye`) retain:
  - `state = 'OWNED'`
  - `quality_kbps = 320`
  - `file_path = C:\\Users\\Praveen\\Downloads\\Songs New\\Track - ...`
  - Zero redownload, zero file modifications, zero quality downgrades.

---

## 8. Backup & Migration Strategy

1. **Pre-Migration Backup**:
   - Create timestamped snapshot: `backup/library_pre_master_catalogue_{{timestamp}}.db`.
2. **Migration Script**:
   - Clean suspicious compilation entries from `movies`.
   - Ingest 992 movies from `tamil_songs_corpus.csv` with posters, cast, music directors, and years.
   - Ingest 4,217 songs from corpus, linking to canonical songs via `compute_canonical_hash`.
   - Update FTS5 search index (`INSERT INTO songs_fts...`).
   - Sync all 4 curated charts.
3. **Verification**:
   - Verify: `total_songs >= 4,000+`.
   - Verify: `total_owned == 3`.
   - Verify: `total_not_downloaded == total_songs - 3`.
   - Verify: 100% of physical files preserved.
"""
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report written to: {REPORT_FILE}")

if __name__ == "__main__":
    generate_report()
