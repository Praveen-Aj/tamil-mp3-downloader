import sqlite3
import os

p = os.path.expandvars(r"%APPDATA%\tamil-mp3-downloader\library.db")
conn = sqlite3.connect(p)
c = conn.cursor()
c.execute("UPDATE songs SET title = ?, title_normalized = ? WHERE id = 3352", ("Kannan Manam Enna", "kannan manam enna"))
conn.commit()
print("Updated rows in AppData DB:", c.rowcount)

if os.path.exists("library.db"):
    local_conn = sqlite3.connect("library.db")
    lc = local_conn.cursor()
    lc.execute("UPDATE songs SET title = ?, title_normalized = ? WHERE id = 3352", ("Kannan Manam Enna", "kannan manam enna"))
    local_conn.commit()
    print("Updated rows in local library.db:", lc.rowcount)
