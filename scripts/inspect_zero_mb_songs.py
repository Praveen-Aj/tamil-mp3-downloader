import os
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
import sqlite3
from config.settings import Settings

s = Settings()
conn = sqlite3.connect(str(s.library_db_path))
cursor = conn.cursor()
titles = ['Lokiverse 2.0', "I'm Scared", 'Anbenum', 'Naa Ready', 'Badass']
for t in titles:
    rows = cursor.execute('SELECT id, title, artist, album, state, file_path, file_size_bytes FROM songs WHERE title LIKE ?', ('%' + t + '%',)).fetchall()
    print(f"\n--- Title: {t} ---")
    for r in rows:
        print(f"  Row: {r}")
        fp = r[5]
        if fp:
            p = Path(fp)
            if not p.is_absolute():
                p = s.output_dir / p
            print(f"    Physical path: {p}, exists: {p.exists()}, size: {p.stat().st_size if p.exists() else 'N/A'}")
