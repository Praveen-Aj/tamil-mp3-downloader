import sqlite3
import os
from pathlib import Path

appdata_path = Path(os.path.expandvars(r'%APPDATA%\tamil-mp3-downloader\library.db'))
conn = sqlite3.connect(appdata_path)
conn.row_factory = sqlite3.Row

# 1. Check owned songs vs physical files
rows = conn.execute("SELECT id, title, file_path, file_size_bytes FROM songs WHERE state = 'OWNED'").fetchall()
print(f"Total owned songs in database: {len(rows)}")
missing = 0
for r in rows:
    fp = Path(r["file_path"]) if r["file_path"] else None
    if not fp or not fp.exists():
        missing += 1

print(f"Physical files missing: {missing}")
assert missing == 0, f"Found {missing} missing physical files!"

# 2. Check track count mismatches
mismatches = conn.execute("""
    SELECT COUNT(*) FROM (
        SELECT m.id, m.title, m.track_count, COUNT(sm.song_id) as actual_count
        FROM movies m
        LEFT JOIN song_movies sm ON m.id = sm.movie_id
        GROUP BY m.id
        HAVING COUNT(sm.song_id) != m.track_count
    )
""").fetchone()[0]
print(f"Track count mismatches in database: {mismatches}")
assert mismatches == 0, "Track count mismatches exist!"

# 3. Check movie release years
moondram = conn.execute("SELECT title, year FROM movies WHERE title LIKE '%Moondram Pirai%'").fetchone()
print(f"Moondram Pirai year in DB: {moondram['year']}")
assert moondram["year"] == 1982

# 4. Check non-musical artists in artists table
bad_singers = conn.execute("""
    SELECT COUNT(*) FROM artists 
    WHERE role = 'singer' AND name IN ('Nelson Dilipkumar', 'Lokesh Kanagaraj', 'Aditya Music Tamil', 'Sony Music South')
""").fetchone()[0]
print(f"Non-musical personas classified as singer: {bad_singers}")
assert bad_singers == 0

conn.close()
print("\nALL DATABASE AND PHYSICAL FILE INTEGRITY CHECKS PASSED PERFECTLY!")
