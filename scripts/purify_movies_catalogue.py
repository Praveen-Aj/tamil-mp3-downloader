"""
Purify Movies Catalogue and Implement Master Catalogue Fixes:
1. Create safety database backup
2. Apply Migration 6 (Movie provenance & multilingual columns)
3. Populate explicit provenance for all movies
4. Re-link genuine songs from OST duplicates & compilations to real Tamil movies
5. Decouple non-movie songs and remove the 89 non-movie entities from movies table
6. Recalculate track_count for all remaining movies
7. Synchronize chart-tamil-classics-top-50 to exactly 50 canonical tracks
8. Verify before/after database metrics
"""

import os
import sys
import shutil
import sqlite3
import csv
import ast
from pathlib import Path
from datetime import datetime

repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root))

from library.database import SQLiteDatabase
from library.charts import ChartDiscoveryService
from library.migrator import DatabaseMigrator
from library.canonical import normalize_string

def purify_catalogue():
    print("=" * 70)
    print("V6 — MASTER CATALOGUE PURIFICATION & AUDIT FIXES")
    print("=" * 70)

    db_path = Path(os.path.expandvars(r'%APPDATA%\tamil-mp3-downloader\library.db'))
    assert db_path.exists(), f"Database not found at {db_path}"

    # 1. Safety Backup
    backup_dir = repo_root / "backup"
    backup_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"library_pre_purification_{timestamp}.db"
    shutil.copy2(db_path, backup_path)
    print(f"[1/8] Safety database backup created: {backup_path} ({backup_path.stat().st_size:,} bytes)")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 2. Before Metrics
    cursor.execute("SELECT COUNT(*) FROM movies")
    before_movies = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM songs")
    before_songs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM songs WHERE state='OWNED' OR (file_path IS NOT NULL AND file_path != '')")
    before_owned = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM chart_entries WHERE chart_id='chart-tamil-classics-top-50'")
    before_classics_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM artists")
    before_artists = cursor.fetchone()[0]

    print("\n--- BEFORE COUNTS ---")
    print(f"Movies: {before_movies}")
    print(f"Songs: {before_songs}")
    print(f"Owned Songs: {before_owned}")
    print(f"Artists: {before_artists}")
    print(f"Evergreen Classics Chart Count: {before_classics_count}")

    # 3. Apply Schema Migration 6 (Movie Provenance Columns)
    print("\n[2/8] Applying Schema Migration 6 for Movie Provenance...")
    cursor.execute("PRAGMA table_info(movies)")
    movie_cols = {row['name'] for row in cursor.fetchall()}

    columns_to_add = [
        ("source", "TEXT DEFAULT 'tamil_songs_corpus'"),
        ("source_movie_url", "TEXT"),
        ("source_movie_image", "TEXT"),
        ("tamil_title", "TEXT"),
        ("english_title", "TEXT"),
    ]
    for col_name, col_def in columns_to_add:
        if col_name not in movie_cols:
            cursor.execute(f"ALTER TABLE movies ADD COLUMN {col_name} {col_def}")
            print(f"  Added column: movies.{col_name}")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_movies_source ON movies(source)")
    cursor.execute("INSERT OR REPLACE INTO schema_version (version, applied_at) VALUES (6, CURRENT_TIMESTAMP)")
    conn.commit()

    # 4. Populate Provenance from Corpus & Known Sources
    print("\n[3/8] Populating Movie Provenance & Multilingual Titles...")
    corpus_path = repo_root / "data" / "reference" / "tamil-songs-corpus" / "tamil_songs_corpus.csv"
    corpus_lookup = {}
    if corpus_path.exists():
        with open(corpus_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            next(reader)
            for row in reader:
                if row:
                    try:
                        data = ast.literal_eval(row[0])
                        eng = data.get("movie_name_eng", "").strip()
                        norm_eng = normalize_string(eng)
                        corpus_lookup[norm_eng] = data
                        # also key by raw lower
                        corpus_lookup[eng.lower()] = data
                    except Exception:
                        pass
    print(f"  Loaded {len(corpus_lookup)} corpus movie records.")

    cursor.execute("SELECT id, title, title_normalized FROM movies")
    all_movies = cursor.fetchall()
    provenance_updates = 0

    for m in all_movies:
        mid = m['id']
        title = m['title']
        norm = m['title_normalized']

        corpus_data = corpus_lookup.get(norm) or corpus_lookup.get(title.lower())
        if corpus_data:
            cursor.execute("""
                UPDATE movies SET
                    source = 'tamil_songs_corpus',
                    source_movie_url = ?,
                    source_movie_image = ?,
                    tamil_title = ?,
                    english_title = ?
                WHERE id = ?
            """, (
                corpus_data.get("movie_url"),
                corpus_data.get("movie_image"),
                corpus_data.get("movie_name_tamil"),
                corpus_data.get("movie_name_eng"),
                mid
            ))
            provenance_updates += 1
        elif mid in [1, 2, 3, 5, 23, 27, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48]:
            cursor.execute("UPDATE movies SET source = 'v5_archive', english_title = ? WHERE id = ?", (title, mid))
            provenance_updates += 1
        else:
            cursor.execute("UPDATE movies SET source = 'chart_discovery', english_title = ? WHERE id = ?", (title, mid))
            provenance_updates += 1

    conn.commit()
    print(f"  Updated provenance for {provenance_updates} movies.")

    # 5. Identify the 89 Non-Movie Entities
    print("\n[4/8] Identifying the 89 Non-Movie Entities...")
    cursor.execute("""
        SELECT id, title, year, track_count FROM movies 
        WHERE title LIKE '%Hits%' 
           OR title LIKE '%Best%' 
           OR title LIKE '%Collection%' 
           OR title LIKE '%Single%' 
           OR title LIKE '%Mix%'
           OR year < 1930
           OR year > 2026
           OR year IS NULL
        ORDER BY id ASC
    """)
    non_movie_rows = cursor.fetchall()
    non_movie_ids = [r['id'] for r in non_movie_rows]
    print(f"  Found exactly {len(non_movie_ids)} non-movie entities.")

    # 6. Re-link Genuine Tamil Songs from OST duplicates & compilations
    print("\n[5/8] Preserving and Re-linking Genuine Tamil Songs...")
    # OST duplicates mapping to genuine Tamil movies:
    # 'Vaaranam Aayiram (Original Motion Picture Soundtrack)' -> 'Vaaranam Aayiram'
    # 'Pathu Thala (Original Motion Picture Soundtrack)' -> 'Pathu Thala'
    # 'Vikram (Original Motion Picture Soundtrack)' -> 'Vikram'
    cursor.execute("SELECT id FROM movies WHERE title_normalized = 'vaaranam aayiram' AND id NOT IN ({})".format(','.join(map(str, non_movie_ids))))
    va_real = cursor.fetchone()
    va_real_id = va_real['id'] if va_real else None

    cursor.execute("SELECT id FROM movies WHERE title_normalized = 'pathu thala' AND id NOT IN ({})".format(','.join(map(str, non_movie_ids))))
    pt_real = cursor.fetchone()
    pt_real_id = pt_real['id'] if pt_real else None

    cursor.execute("SELECT id FROM movies WHERE title_normalized = 'vikram' AND id NOT IN ({})".format(','.join(map(str, non_movie_ids))))
    vikram_real = cursor.fetchone()
    vikram_real_id = vikram_real['id'] if vikram_real else None

    relinked_songs = 0
    decoupled_songs = 0

    for nmid in non_movie_ids:
        cursor.execute("SELECT song_id FROM song_movies WHERE movie_id = ?", (nmid,))
        song_links = cursor.fetchall()
        for sl in song_links:
            sid = sl['song_id']
            # Check if this was an OST duplicate
            if nmid == 1213 and va_real_id:
                cursor.execute("INSERT OR REPLACE INTO song_movies (song_id, movie_id) VALUES (?, ?)", (sid, va_real_id))
                relinked_songs += 1
            elif nmid == 193 and pt_real_id:
                cursor.execute("INSERT OR REPLACE INTO song_movies (song_id, movie_id) VALUES (?, ?)", (sid, pt_real_id))
                relinked_songs += 1
            elif nmid == 203 and vikram_real_id:
                cursor.execute("INSERT OR REPLACE INTO song_movies (song_id, movie_id) VALUES (?, ?)", (sid, vikram_real_id))
                relinked_songs += 1
            else:
                # Check if the song's album or title belongs to a genuine movie
                cursor.execute("SELECT title, album FROM songs WHERE id = ?", (sid,))
                sinfo = cursor.fetchone()
                if sinfo:
                    norm_alb = normalize_string(sinfo['album'] or '')
                    cursor.execute("SELECT id FROM movies WHERE title_normalized = ? AND id NOT IN ({})".format(','.join(map(str, non_movie_ids))), (norm_alb,))
                    real_m = cursor.fetchone()
                    if real_m:
                        cursor.execute("INSERT OR REPLACE INTO song_movies (song_id, movie_id) VALUES (?, ?)", (sid, real_m['id']))
                        relinked_songs += 1
                    else:
                        decoupled_songs += 1

    print(f"  Re-linked {relinked_songs} songs to genuine Tamil cinema movies.")
    print(f"  Decoupled {decoupled_songs} non-movie/single songs while preserving songs in database.")

    # Remove song_movies, movie_composers, movie_actors for the 89 entities
    id_placeholders = ','.join('?' * len(non_movie_ids))
    cursor.execute(f"DELETE FROM song_movies WHERE movie_id IN ({id_placeholders})", non_movie_ids)
    cursor.execute(f"DELETE FROM movie_composers WHERE movie_id IN ({id_placeholders})", non_movie_ids)
    cursor.execute(f"DELETE FROM movie_actors WHERE movie_id IN ({id_placeholders})", non_movie_ids)

    # Delete the 89 non-movie entities from movies table
    cursor.execute(f"DELETE FROM movies WHERE id IN ({id_placeholders})", non_movie_ids)
    deleted_movies = cursor.rowcount
    conn.commit()
    print(f"[6/8] Purified Movies Catalogue: Removed {deleted_movies} non-movie entities from movies table.")

    # 7. Recalculate track_count on remaining movies
    print("\n[7/8] Recalculating Movie Track Counts...")
    cursor.execute("""
        UPDATE movies SET track_count = (
            SELECT COUNT(DISTINCT sm.song_id)
            FROM song_movies sm
            WHERE sm.movie_id = movies.id
        )
    """)
    conn.commit()
    print("  Track counts updated.")

    conn.close()

    # 8. Re-sync Curated Classics Chart to 50 tracks
    print("\n[8/8] Synchronizing Curated Classics Chart (chart-tamil-classics-top-50) to 50 Tracks...")
    db = SQLiteDatabase(db_path)
    db.connect()
    discovery = ChartDiscoveryService(db)
    chart_id = discovery.sync_curated_classics_chart()
    print(f"  Synchronized chart: {chart_id}")

    # Re-query after metrics
    entries = db.get_chart_entries("chart-tamil-classics-top-50")
    print(f"  Curated Classics Chart Entry Count: {len(entries)}")
    assert len(entries) == 50, f"Expected 50 entries, got {len(entries)}"

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM movies")
    after_movies = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM songs")
    after_songs = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM songs WHERE state='OWNED' OR (file_path IS NOT NULL AND file_path != '')")
    after_owned = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM artists")
    after_artists = cursor.fetchone()[0]

    cursor.execute("""
        SELECT COUNT(*) FROM movies 
        WHERE title LIKE '%Hits%' 
           OR title LIKE '%Best%' 
           OR title LIKE '%Collection%' 
           OR title LIKE '%Single%' 
           OR title LIKE '%Mix%'
           OR year < 1930
           OR year > 2026
           OR year IS NULL
    """)
    remaining_suspicious = cursor.fetchone()[0]

    cursor.execute("SELECT source, COUNT(*) FROM movies GROUP BY source")
    provenance_breakdown = cursor.fetchall()

    conn.close()
    db.close()

    print("\n" + "=" * 70)
    print("PURIFICATION & AUDIT FIXES SUMMARY")
    print("=" * 70)
    print(f"Movies: {before_movies} -> {after_movies} (Removed: {before_movies - after_movies} non-movie entities)")
    print(f"Suspicious / Non-Movie Entities Remaining: {remaining_suspicious}")
    print(f"Songs in DB: {before_songs} -> {after_songs} (Preserved all songs: {before_songs == after_songs})")
    print(f"Owned Songs: {before_owned} -> {after_owned} (Preserved 100% owned files: {before_owned == after_owned})")
    print(f"Artists in DB: {before_artists} -> {after_artists}")
    print(f"Evergreen Classics Chart Count: {before_classics_count} -> {len(entries)} (Expected: 50)")
    print("\nMovie Provenance Breakdown:")
    for src, count in provenance_breakdown:
        print(f"  {src}: {count} movies")
    print("=" * 70)

if __name__ == "__main__":
    purify_catalogue()
