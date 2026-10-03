"""
Phase 0 Comprehensive Audit Script for Master Catalogue and Discovery Data Foundation.
Inspects:
- Active production SQLite database (AppData/Roaming/tamil-mp3-downloader/library.db)
- Reference Tamil Songs Corpus (data/reference/tamil-songs-corpus/)
- V5 architecture and historical data
- Artwork resolution rules & causes of incorrect artwork
- Chart subsystem and reasons for tiny datasets
- Deduplication and canonical identity matching
"""

import os
import sys
import sqlite3
import csv
from pathlib import Path
from collections import Counter

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = Path(os.environ.get("APPDATA", "")) / "tamil-mp3-downloader" / "library.db"
CORPUS_CSV = Path("data/reference/tamil-songs-corpus/tamil_songs_corpus.csv")
CORPUS_PREPROCESSED = Path("data/reference/tamil-songs-corpus/tamil_songs_corpus_preprocessed_data.csv")

def audit_database():
    print(f"\n==========================================")
    print(f"1. AUDITING PRODUCTION DATABASE: {DB_PATH}")
    print(f"==========================================")
    if not DB_PATH.exists():
        print(f"ERROR: DB not found at {DB_PATH}")
        return

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
        print(f"  {t:20s}: {counts[t]}")

    # Song state breakdown
    c.execute("SELECT state, COUNT(*) FROM songs GROUP BY state")
    states = dict(c.fetchall())
    print(f"\n  Song states: {states}")

    # Owned songs inspection
    c.execute("SELECT id, title, artist, album, file_path, file_size_bytes, quality_kbps FROM songs WHERE state='OWNED'")
    owned_songs = c.fetchall()
    print(f"\n  Owned songs ({len(owned_songs)}):")
    for s in owned_songs:
        print(f"    ID {s[0]}: '{s[1]}' by '{s[2]}' (Album: '{s[3]}') | Path: {s[4]} | Quality: {s[6]} kbps")

    # Movies breakdown
    c.execute("SELECT COUNT(DISTINCT year), MIN(year), MAX(year) FROM movies WHERE year IS NOT NULL")
    yr_info = c.fetchone()
    print(f"\n  Movies year range: min={yr_info[1]}, max={yr_info[2]} (distinct years: {yr_info[0]})")
    c.execute("SELECT year, COUNT(*) FROM movies GROUP BY year ORDER BY COUNT(*) DESC LIMIT 10")
    print(f"  Top movie years: {c.fetchall()}")

    # Check for suspicious movie names (compilations, playlists, etc.)
    c.execute("SELECT id, title, year, poster_url FROM movies LIMIT 20")
    sample_movies = c.fetchall()
    print(f"\n  Sample 10 movies:")
    for m in sample_movies[:10]:
        print(f"    ID {m[0]}: '{m[1]}' ({m[2]}) | Poster: {m[3][:60] if m[3] else 'None'}")

    # Check Arabic Kuthu specifically
    c.execute("""
        SELECT s.id, s.title, s.artist, s.album, sm.movie_id, m.title, m.year, m.poster_url
        FROM songs s
        LEFT JOIN song_movies sm ON s.id = sm.song_id
        LEFT JOIN movies m ON sm.movie_id = m.id
        WHERE s.title LIKE '%Arabic Kuthu%'
    """)
    arabic_songs = c.fetchall()
    print(f"\n  'Arabic Kuthu' song records:")
    for s in arabic_songs:
        print(f"    Song ID {s[0]}: '{s[1]}' | Artist: '{s[2]}' | Album: '{s[3]}' | Movie: ID={s[4]}, Title='{s[5]}', Year={s[6]}, Poster={s[7]}")

    # Charts breakdown
    c.execute("SELECT id, title, chart_type, provider_name, snapshot_date FROM charts")
    charts = c.fetchall()
    print(f"\n  Charts ({len(charts)}):")
    for ch in charts:
        c.execute("SELECT COUNT(*) FROM chart_entries WHERE chart_id=?", (ch[0],))
        entry_cnt = c.fetchone()[0]
        c.execute("SELECT MIN(rank), MAX(rank) FROM chart_entries WHERE chart_id=?", (ch[0],))
        ranks = c.fetchone()
        print(f"    Chart '{ch[0]}' ('{ch[1]}') | Type: {ch[2]} | Provider: {ch[3]} | Entries: {entry_cnt} (Ranks: {ranks[0]}-{ranks[1]})")

    # Song-Movie relationship check
    c.execute("SELECT COUNT(DISTINCT song_id) FROM song_movies")
    songs_with_movie = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM song_movies")
    song_movies_count = c.fetchone()[0]
    print(f"\n  Songs with linked movie: {songs_with_movie} / {counts['songs']}")
    print(f"  Explicit song_movies link rows: {song_movies_count}")

    conn.close()

def audit_corpus():
    print(f"\n==========================================")
    print(f"2. AUDITING REFERENCE TAMIL SONGS CORPUS")
    print(f"==========================================")
    if not CORPUS_CSV.exists():
        print(f"ERROR: {CORPUS_CSV} does not exist.")
        return

    with open(CORPUS_CSV, mode="r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        rows = list(reader)

    print(f"  Total records in raw corpus: {len(rows)}")
    print(f"  Columns: {fields}")

    # Distinct movies and songs
    movies = set()
    songs = set()
    years = Counter()
    has_image = 0
    for r in rows:
        m = (r.get("movie") or "").strip()
        s = (r.get("song_title") or "").strip()
        y = (r.get("year") or "").strip()
        img = (r.get("movie_image") or "").strip()
        if m:
            movies.add(m)
        if s:
            songs.add(s)
        if y:
            years[y] += 1
        if img:
            has_image += 1

    print(f"  Unique movie names in corpus: {len(movies)}")
    print(f"  Unique song titles in corpus: {len(songs)}")
    print(f"  Records with movie_image: {has_image} / {len(rows)}")
    print(f"  Top 10 years in corpus: {years.most_common(10)}")

    # Inspect sample record
    print("\n  Sample record:")
    sample = rows[0]
    for k, v in sample.items():
        if isinstance(v, str) and len(v) > 80:
            print(f"    {k}: {v[:80]}...")
        else:
            print(f"    {k}: {v}")

if __name__ == "__main__":
    audit_database()
    audit_corpus()
