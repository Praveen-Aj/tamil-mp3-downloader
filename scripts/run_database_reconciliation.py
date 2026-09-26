import os
import sqlite3
from pathlib import Path
from library.database import SQLiteDatabase

appdata_path = Path(os.path.expandvars(r'%APPDATA%\tamil-mp3-downloader\library.db'))
local_path = Path("library.db").resolve()

for db_path in [appdata_path, local_path]:
    if not db_path.exists():
        print(f"Skipping {db_path} (does not exist)")
        continue
    print(f"\n==========================================")
    print(f"Running reconciliation on: {db_path}")
    print(f"==========================================")
    db = SQLiteDatabase(db_path)
    db.connect()

    # 1. Track counts
    before_tc = db._conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT m.id FROM movies m
            LEFT JOIN song_movies sm ON m.id = sm.movie_id
            GROUP BY m.id
            HAVING COUNT(sm.song_id) != m.track_count
        )
    """).fetchone()[0]
    print(f"Before track count mismatches: {before_tc}")
    updated_tc = db.reconcile_movie_track_counts()
    after_tc = db._conn.execute("""
        SELECT COUNT(*) FROM (
            SELECT m.id FROM movies m
            LEFT JOIN song_movies sm ON m.id = sm.movie_id
            GROUP BY m.id
            HAVING COUNT(sm.song_id) != m.track_count
        )
    """).fetchone()[0]
    print(f"Updated {updated_tc} movie track counts. After mismatches: {after_tc}")

    # 2. Release years
    before_years = db._conn.execute("SELECT COUNT(*) FROM movies WHERE year IS NULL").fetchone()[0]
    print(f"Before NULL release years: {before_years}")
    recovered_years = db.reconcile_movie_release_years()
    after_years = db._conn.execute("SELECT COUNT(*) FROM movies WHERE year IS NULL").fetchone()[0]
    print(f"Recovered {recovered_years} movie release years. Remaining NULL (no authoritative data): {after_years}")

    # 3. Artist duplicates
    merged = db.reconcile_artist_duplicates()
    print(f"Merged {merged} duplicate artists.")

    # 4. Filesystem integrity
    reconciled_files = db.reconcile_filesystem_integrity()
    print(f"Reconciled {reconciled_files} filesystem records.")

    db.close()
print("\nDatabase reconciliation complete!")
