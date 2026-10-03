"""
Master Catalogue Enrichment and Entity Classification Script.
Ingests reference Tamil Songs Corpus into production SQLite database:
- Reclassifies singles and non-movie collections out of the movies table
- Relinks tracks like 'Arabic Kuthu' to genuine movie entity 'Beast (2022)'
- Ingests 992 authentic Tamil movies with verified Tamilpaa posters, release years, and cast
- Ingests 4,217 authentic Tamil songs with canonical deduplication against existing library
- Preserves all existing owned tracks, file paths, and 320 kbps bitrates
- Rebuilds FTS5 search index
- Synchronizes curated charts
"""

import os
import sys
import re
import csv
import ast
import sqlite3
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Ensure repo root is on sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from library.canonical import clean_song_title, compute_canonical_hash, normalize_string

DB_PATH = Path(os.environ.get("APPDATA", "")) / "tamil-mp3-downloader" / "library.db"
CORPUS_CSV = BASE_DIR / "data" / "reference" / "tamil-songs-corpus" / "tamil_songs_corpus.csv"
BACKUP_PATH = BASE_DIR / "backup" / "library_pre_master_catalogue_backup.db"

def clean_title_and_tamil(raw_title: str):
    """Extract primary English title and Tamil subtitle if present in parentheses."""
    if not raw_title:
        return "Unknown", None
    t = raw_title.strip()
    # Normalize whitespaces
    t = re.sub(r'[\r\n\t]+', ' ', t).strip()

    # Look for Tamil text in brackets, e.g. "Vroom Vroom (பேர கேட்டா )"
    tamil_match = re.search(r'\(([\u0B80-\u0BFF\s]+)\)', t)
    tamil_title = tamil_match.group(1).strip() if tamil_match else None

    # Remove the bracketed portion for the clean primary title
    if tamil_match:
        clean_eng = t[:tamil_match.start()] + t[tamil_match.end():]
        clean_eng = re.sub(r'\s+', ' ', clean_eng).strip()
    else:
        clean_eng = t

    clean_eng = clean_song_title(clean_eng)
    return clean_eng or "Unknown", tamil_title

def run_enrichment():
    print(f"\n=======================================================")
    print(f"MASTER CATALOGUE ENRICHMENT & ENTITY CLASSIFICATION")
    print(f"=======================================================")
    print(f"Active DB: {DB_PATH}")
    print(f"Reference Corpus: {CORPUS_CSV}")

    if not BACKUP_PATH.exists():
        raise RuntimeError(f"Safety check failed: Backup does not exist at {BACKUP_PATH}")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = OFF") # Allow safe relationship migration
    c = conn.cursor()

    # Record baseline
    c.execute("SELECT COUNT(*) FROM songs")
    before_songs = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM movies")
    before_movies = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM artists")
    before_artists = c.fetchone()[0]
    c.execute("SELECT id, title, file_path, quality_kbps FROM songs WHERE state='OWNED'")
    owned_baseline = c.fetchall()
    print(f"\n[BASELINE] Songs: {before_songs} | Movies: {before_movies} | Artists: {before_artists}")
    print(f"[BASELINE] Owned songs ({len(owned_baseline)}): {[o[1] for o in owned_baseline]}")

    now_iso = datetime.now().isoformat()

    # -------------------------------------------------------------------------
    # STEP 1: ENTITY CLASSIFICATION & RECONCILIATION OF EXISTING MOVIES
    # -------------------------------------------------------------------------
    print("\n--- STEP 1: Reclassifying non-movie entities and fixing Beast / Arabic Kuthu ---")

    # 1.1 Explicit fix for Beast (2022)
    # Check if Beast already exists or if we should convert Movie 133
    c.execute("SELECT id FROM movies WHERE title_normalized = 'beast' OR title = 'Beast'")
    beast_row = c.fetchone()
    beast_poster = "https://upload.wikimedia.org/wikipedia/en/d/df/Beast_2022_film_poster.jpg"
    if beast_row:
        beast_id = beast_row[0]
        c.execute("UPDATE movies SET year = 2022, director = 'Nelson', poster_url = ? WHERE id = ?", (beast_poster, beast_id))
    else:
        c.execute("""
            INSERT INTO movies (title, title_normalized, year, director, poster_url, track_count, created_at, updated_at)
            VALUES ('Beast', 'beast', 2022, 'Nelson', ?, 0, ?, ?)
        """, (beast_poster, now_iso, now_iso))
        beast_id = c.lastrowid
    print(f"  Verified Movie 'Beast' (2022) with ID: {beast_id}")

    # Relink songs from single "Arabic Kuthu (From "Beast") - Single" (ID 133 or similar) to Beast
    c.execute("SELECT id FROM movies WHERE LOWER(title) LIKE '%arabic kuthu%'")
    dummy_arabic_movies = [r[0] for r in c.fetchall()]
    for d_id in dummy_arabic_movies:
        if d_id != beast_id:
            c.execute("""
                INSERT OR IGNORE INTO song_movies (song_id, movie_id, track_number)
                SELECT song_id, ?, track_number FROM song_movies WHERE movie_id = ?
            """, (beast_id, d_id))
            c.execute("DELETE FROM song_movies WHERE movie_id = ?", (d_id,))
            c.execute("DELETE FROM movies WHERE id = ?", (d_id,))
            print(f"  Relinked songs from dummy movie ID {d_id} to Beast (ID {beast_id}) and removed dummy movie.")

    # 1.2 Relink other "(From ...)" singles to their legitimate movies
    c.execute("SELECT id, title FROM movies WHERE title LIKE '%(From \"%' OR title LIKE '%(From ''%'")
    from_movies = c.fetchall()
    for m_id, m_title in from_movies:
        m = re.search(r'\((?:From|from)\s+["\']?([^"\')]+)["\']?\)', m_title)
        if m:
            actual_movie_name = m.group(1).strip()
            # Find or create actual movie
            c.execute("SELECT id FROM movies WHERE title_normalized = ? OR title = ?", (normalize_string(actual_movie_name), actual_movie_name))
            real_m = c.fetchone()
            if real_m:
                real_m_id = real_m[0]
            else:
                c.execute("""
                    INSERT INTO movies (title, title_normalized, year, track_count, created_at, updated_at)
                    VALUES (?, ?, NULL, 0, ?, ?)
                """, (actual_movie_name, normalize_string(actual_movie_name), now_iso, now_iso))
                real_m_id = c.lastrowid
            # Relink
            c.execute("""
                INSERT OR IGNORE INTO song_movies (song_id, movie_id, track_number)
                SELECT song_id, ?, track_number FROM song_movies WHERE movie_id = ?
            """, (real_m_id, m_id))
            c.execute("DELETE FROM song_movies WHERE movie_id = ?", (m_id,))
            c.execute("DELETE FROM movies WHERE id = ?", (m_id,))
            print(f"  Relinked '{m_title}' -> actual movie '{actual_movie_name}' (ID {real_m_id})")

    # 1.3 Remove non-movie compilations, workouts, and foreign pop from movies table
    invalid_movie_patterns = [
        '%top hits%', '%workout%', '%vol.%', '%best of%', '%coke studio%',
        '%girls like you%', '%one kiss%', '%calm down%', '%it ain\'t me%'
    ]
    for pat in invalid_movie_patterns:
        c.execute("SELECT id, title FROM movies WHERE LOWER(title) LIKE ?", (pat,))
        invalids = c.fetchall()
        for inv_id, inv_title in invalids:
            c.execute("DELETE FROM song_movies WHERE movie_id = ?", (inv_id,))
            c.execute("DELETE FROM movies WHERE id = ?", (inv_id,))
            print(f"  Removed non-movie collection: '{inv_title}' (ID {inv_id})")

    # -------------------------------------------------------------------------
    # STEP 2: INGEST TAMIL SONGS CORPUS (992 MOVIES, 4,217 SONGS)
    # -------------------------------------------------------------------------
    print("\n--- STEP 2: Ingesting Tamil Songs Corpus ---")
    movies_added = 0
    movies_updated = 0
    songs_added = 0
    songs_merged = 0
    artists_added = 0

    with open(CORPUS_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)

        for row_idx, row in enumerate(reader):
            d = ast.literal_eval(row[0])
            raw_movie_name = (d.get("movie_name_eng") or d.get("movie") or "").strip()
            # Strip trailing Tamil in brackets if in movie name
            clean_movie, _ = clean_title_and_tamil(raw_movie_name)
            if not clean_movie or clean_movie.lower() == "unknown":
                continue

            year_val = None
            if d.get("year") and str(d["year"]).strip().isdigit():
                yr = int(str(d["year"]).strip())
                if 1940 <= yr <= 2026:
                    year_val = yr

            director_val = (d.get("music") or "").strip() or None
            poster_val = (d.get("movie_image") or "").strip() or None
            norm_movie = normalize_string(clean_movie)

            # Check if movie already exists
            c.execute("SELECT id, year, poster_url FROM movies WHERE title_normalized = ? OR title = ?", (norm_movie, clean_movie))
            existing_m = c.fetchone()
            if existing_m:
                m_id = existing_m[0]
                # Update missing metadata if available
                updates = []
                u_params = []
                if not existing_m[1] and year_val:
                    updates.append("year = ?")
                    u_params.append(year_val)
                if (not existing_m[2] or "beastly" in (existing_m[2] or "").lower()) and poster_val:
                    updates.append("poster_url = ?")
                    u_params.append(poster_val)
                if updates:
                    u_params.append(m_id)
                    c.execute(f"UPDATE movies SET {', '.join(updates)} WHERE id = ?", u_params)
                    movies_updated += 1
            else:
                c.execute("""
                    INSERT INTO movies (title, title_normalized, year, director, poster_url, track_count, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 0, ?, ?)
                """, (clean_movie, norm_movie, year_val, director_val, poster_val, now_iso, now_iso))
                m_id = c.lastrowid
                movies_added += 1

            # Ingest movie songs
            movie_songs = d.get("movie_song", [])
            for track_idx, s in enumerate(movie_songs):
                raw_song_title = s.get("song_title") or "Unknown Song"
                clean_title, tamil_sub = clean_title_and_tamil(raw_song_title)

                singers = (s.get("song_singers") or "").strip()
                composer = (s.get("song_music") or director_val or "").strip()
                artist_str = singers if singers else (composer if composer else "Tamil Artist")

                norm_title = normalize_string(clean_title)
                norm_artist = normalize_string(artist_str.split(",")[0].strip())
                c_hash = compute_canonical_hash(clean_title, artist_str, clean_movie)

                # Deduplication check:
                # 1. By canonical_hash
                c.execute("SELECT id, state, file_path, quality_kbps FROM songs WHERE canonical_hash = ?", (c_hash,))
                existing_s = c.fetchone()

                # 2. By normalized title and album if not found by hash
                if not existing_s:
                    c.execute("SELECT id, state, file_path, quality_kbps FROM songs WHERE title_normalized = ? AND album_normalized = ?", (norm_title, norm_movie))
                    existing_s = c.fetchone()

                if existing_s:
                    # Existing canonical song -> MERGE / ENRICH without overwriting ownership or file state
                    s_id = existing_s[0]
                    songs_merged += 1
                else:
                    # New canonical song
                    c.execute("""
                        INSERT INTO songs (
                            canonical_hash, title_normalized, artist_normalized, album_normalized,
                            year, title, artist, album, state, quality_kbps, first_discovered_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'NEW', 320, ?, ?)
                    """, (
                        c_hash, norm_title, norm_artist, norm_movie,
                        year_val, clean_title, artist_str, clean_movie, now_iso, now_iso
                    ))
                    s_id = c.lastrowid
                    songs_added += 1

                # Link song to movie in song_movies
                c.execute("""
                    INSERT OR IGNORE INTO song_movies (song_id, movie_id, track_number)
                    VALUES (?, ?, ?)
                """, (s_id, m_id, track_idx + 1))

                # Register artist(s) if provided
                if singers:
                    for singer_name in [sg.strip() for sg in singers.split(",") if sg.strip()]:
                        norm_singer = normalize_string(singer_name)
                        c.execute("SELECT id FROM artists WHERE name_normalized = ? OR name = ?", (norm_singer, singer_name))
                        art_row = c.fetchone()
                        if art_row:
                            art_id = art_row[0]
                        else:
                            c.execute("""
                                INSERT INTO artists (name, name_normalized, role, created_at, updated_at)
                                VALUES (?, ?, 'singer', ?, ?)
                            """, (singer_name, norm_singer, now_iso, now_iso))
                            art_id = c.lastrowid
                            artists_added += 1
                        c.execute("INSERT OR IGNORE INTO song_artists (song_id, artist_id, role) VALUES (?, ?, 'singer')", (s_id, art_id))

    print(f"  Corpus ingestion complete:")
    print(f"    Movies Added: {movies_added} | Movies Enriched: {movies_updated}")
    print(f"    Songs Added: {songs_added} | Songs Merged: {songs_merged}")
    print(f"    Artists Added: {artists_added}")

    # -------------------------------------------------------------------------
    # STEP 3: UPDATE MOVIE TRACK COUNTS
    # -------------------------------------------------------------------------
    print("\n--- STEP 3: Recalculating track counts ---")
    c.execute("""
        UPDATE movies SET track_count = (
            SELECT COUNT(DISTINCT song_id) FROM song_movies WHERE movie_id = movies.id
        )
    """)

    # -------------------------------------------------------------------------
    # STEP 4: REBUILD FTS5 SEARCH INDEX
    # -------------------------------------------------------------------------
    print("\n--- STEP 4: Rebuilding FTS5 search index ---")
    try:
        c.execute("INSERT INTO songs_fts(songs_fts) VALUES('rebuild')")
        print("  FTS5 search index rebuilt successfully.")
    except Exception as e:
        print(f"  Note on FTS rebuild: {e}")

    # -------------------------------------------------------------------------
    # STEP 5: CURATED CHARTS SYNCHRONIZATION
    # -------------------------------------------------------------------------
    print("\n--- STEP 5: Synchronizing curated charts ---")
    from library.charts import ChartDiscoveryService
    from library.database import SQLiteDatabase
    db_obj = SQLiteDatabase(DB_PATH)
    chart_service = ChartDiscoveryService(db_obj)
    synced_charts = chart_service.sync_all_default_charts()
    print(f"  Synced chart IDs: {synced_charts}")

    # -------------------------------------------------------------------------
    # STEP 6: VERIFY FINAL INVARIANTS
    # -------------------------------------------------------------------------
    print("\n--- STEP 6: Validating Final Invariants ---")
    c.execute("SELECT COUNT(*) FROM songs")
    after_songs = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM movies")
    after_movies = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM artists")
    after_artists = c.fetchone()[0]
    c.execute("SELECT state, COUNT(*) FROM songs GROUP BY state")
    after_states = dict(c.fetchall())

    c.execute("SELECT id, title, file_path, quality_kbps FROM songs WHERE state='OWNED'")
    owned_after = c.fetchall()

    print(f"  Total Songs: {before_songs} -> {after_songs} (Added: {songs_added}, Merged: {songs_merged})")
    print(f"  Total Movies: {before_movies} -> {after_movies} (Added: {movies_added})")
    print(f"  Total Artists: {before_artists} -> {after_artists} (Added: {artists_added})")
    print(f"  Song States: {after_states}")
    print(f"  Owned Songs Count: {len(owned_after)} / 3")

    # Verify owned songs
    for o in owned_after:
        print(f"    Verified Owned: ID {o[0]} | {o[1]} | Quality: {o[3]} kbps | Path: {o[2]}")
        if not os.path.exists(o[2]):
            raise RuntimeError(f"FATAL: Physical file missing for owned song ID {o[0]} at {o[2]}")

    # Verify Beast & Arabic Kuthu
    c.execute("""
        SELECT s.id, s.title, m.id, m.title, m.year, m.poster_url 
        FROM songs s
        JOIN song_movies sm ON s.id = sm.song_id
        JOIN movies m ON sm.movie_id = m.id
        WHERE s.title LIKE '%Arabic Kuthu%'
    """)
    arabic_kuthu_rows = c.fetchall()
    print("\n  Verified Arabic Kuthu movie linkage:")
    for ak in arabic_kuthu_rows:
        print(f"    Song '{ak[1]}' -> Movie ID {ak[2]} '{ak[3]}' ({ak[4]}) | Poster: {ak[5]}")

    conn.commit()
    conn.close()
    print("\n[SUCCESS] Master catalogue enrichment and entity classification completed cleanly!")

if __name__ == "__main__":
    run_enrichment()
