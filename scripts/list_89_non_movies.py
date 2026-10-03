import os
import sqlite3
from pathlib import Path

db_path = Path(os.path.expandvars(r'%APPDATA%\tamil-mp3-downloader\library.db'))
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

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
rows = cursor.fetchall()
print(f"Total matching suspicious criteria: {len(rows)}")

total_linked_songs = 0
for r in rows:
    mid, title, year, track_count = r
    cursor.execute("""
        SELECT s.id, s.title, s.artist, s.album, s.state, s.file_path 
        FROM songs s
        JOIN song_movies sm ON s.id = sm.song_id
        WHERE sm.movie_id = ?
    """, (mid,))
    songs = cursor.fetchall()
    total_linked_songs += len(songs)
    owned = [s for s in songs if s[4] == 'OWNED' or s[5]]
    print(f"ID {mid:4d} | Tracks: {track_count:2d} | Linked: {len(songs):2d} | Owned: {len(owned)} | Title: '{title}' ({year})")
    if owned:
        print(f"   *** WARNING: CONTAINS OWNED SONGS: {owned} ***")

print(f"\nTotal linked songs across all {len(rows)} suspicious movie entities: {total_linked_songs}")

# Check provenance of movies
cursor.execute("PRAGMA table_info(movies)")
cols = [c[1] for c in cursor.fetchall()]
print(f"Movies columns: {cols}")

conn.close()
