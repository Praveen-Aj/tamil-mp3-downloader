import os
import sys
import sqlite3
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import Settings

settings = Settings()
appdata_db = settings.library_db_path
local_db = PROJECT_ROOT / "library.db"

print("=" * 60)
print("AUDIT: DATABASES AND COUNTS")
print("=" * 60)
print(f"Settings library_db_path: {appdata_db} (exists: {appdata_db.exists()})")
print(f"Local library_db_path: {local_db} (exists: {local_db.exists()})")
print(f"Authoritative output_dir: {settings.output_dir} (exists: {settings.output_dir.exists()})")

def audit_db(db_path: Path):
    if not db_path.exists():
        print(f"Database {db_path} does not exist.")
        return
    print(f"\n--- Inspecting {db_path} ---")
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    tables = [row[0] for row in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"Tables found: {tables}")

    counts = {}
    for t in tables:
        try:
            cnt = cursor.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            counts[t] = cnt
        except Exception as e:
            counts[t] = f"Error: {e}"
    for t, cnt in counts.items():
        print(f"  {t}: {cnt}")

    # Inspect songs
    if "songs" in tables:
        downloaded = cursor.execute("SELECT COUNT(*) FROM songs WHERE state IN ('DOWNLOADED', 'OWNED')").fetchone()[0]
        with_path = cursor.execute("SELECT COUNT(*) FROM songs WHERE file_path IS NOT NULL AND file_path != ''").fetchone()[0]
        zero_size = cursor.execute("SELECT COUNT(*) FROM songs WHERE state IN ('DOWNLOADED', 'OWNED') AND (file_size_bytes IS NULL OR file_size_bytes = 0)").fetchone()[0]
        print(f"  Songs downloaded/owned (state): {downloaded}")
        print(f"  Songs with file_path: {with_path}")
        print(f"  Downloaded songs with 0 or NULL file_size_bytes: {zero_size}")

        # Sample downloaded songs with 0 size
        sample_zeros = cursor.execute("SELECT id, title, artist, file_path, file_size_bytes, state FROM songs WHERE state IN ('DOWNLOADED', 'OWNED') AND (file_size_bytes IS NULL OR file_size_bytes = 0) LIMIT 5").fetchall()
        print(f"  Sample zero-size downloaded songs: {sample_zeros}")

        # All states count
        state_counts = cursor.execute("SELECT state, COUNT(*) FROM songs GROUP BY state").fetchall()
        print(f"  Song states: {state_counts}")

    # Inspect artists
    if "artists" in tables:
        rahman_artists = cursor.execute("SELECT id, name, name_normalized, role FROM artists WHERE name LIKE '%Rahman%'").fetchall()
        print(f"  Rahman artists in artists table: {rahman_artists}")

    if "songs" in tables:
        rahman_songs = cursor.execute("SELECT id, title, artist, file_path, state FROM songs WHERE artist LIKE '%Rahman%'").fetchall()
        print(f"  Total songs with artist LIKE '%Rahman%': {len(rahman_songs)}")
        for s in rahman_songs[:10]:
            print(f"    Song: {s}")

    # Inspect charts
    if "charts" in tables:
        charts = cursor.execute("SELECT * FROM charts").fetchall()
        print(f"  Charts: {charts}")
    if "chart_entries" in tables:
        entries = cursor.execute("SELECT COUNT(*) FROM chart_entries").fetchone()[0]
        print(f"  Chart entries: {entries}")

    # Inspect playlists
    if "playlists" in tables:
        playlists = cursor.execute("SELECT * FROM playlists").fetchall()
        print(f"  Playlists: {playlists}")

    conn.close()

if appdata_db.exists():
    audit_db(appdata_db)

if local_db.exists() and local_db != appdata_db:
    audit_db(local_db)

# Check physical files in downloads folder
dl_dir = settings.output_dir
print(f"\n--- Checking physical files in {dl_dir} ---")
if dl_dir.exists():
    files = list(dl_dir.glob("**/*.*"))
    audio_files = [f for f in files if f.suffix.lower() in ('.mp3', '.m4a', '.opus', '.webm', '.flac')]
    print(f"Total files in downloads: {len(files)}, audio files: {len(audio_files)}")
    for af in audio_files[:10]:
        print(f"  {af.name} ({af.stat().st_size} bytes)")
else:
    print(f"Download directory does not exist: {dl_dir}")
