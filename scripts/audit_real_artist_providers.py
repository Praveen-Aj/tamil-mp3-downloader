import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scrapers.masstamilan import MassTamilanScraper
from scrapers.tamilmp3 import Tamilmp3Scraper
from scrapers.friendstamilmp3 import FriendsTamilMP3Scraper
from scrapers.kollysongs import KollySongsScraper
from scrapers.isaimini import IsaiminiScraper

artists_to_test = [
    "A. R. Rahman",
    "Anirudh Ravichander",
    "Harris Jayaraj",
    "Yuvan Shankar Raja",
    "Ilaiyaraaja",
    "Hiphop Tamizha",
]

print("=" * 70)
print("AUDITING REAL EXTERNAL SCRAPERS FOR ARTISTS")
print("=" * 70)

scrapers = {
    "masstamilan": MassTamilanScraper(),
    "tamilmp3": Tamilmp3Scraper(),
    "friendstamilmp3": FriendsTamilMP3Scraper(),
    "kollysongs": KollySongsScraper(),
    "isaimini": IsaiminiScraper(),
}

# Test connection for each scraper
for name, s in scrapers.items():
    try:
        ok = s.test_connection()
        print(f"Scraper [{name}] connection: {'ONLINE' if ok else 'OFFLINE'} (base_url: {s.base_url})")
    except Exception as e:
        print(f"Scraper [{name}] connection ERROR: {e}")

# Check search/category support for artists
for name, s in scrapers.items():
    print(f"\n--- Checking scraper [{name}] capabilities ---")
    has_search = hasattr(s, "search")
    print(f"  has search: {has_search}")
    for artist in artists_to_test:
        if has_search:
            try:
                results = s.search(artist)
                print(f"  search('{artist}'): {len(results)} albums/results returned")
                if results:
                    first = results[0]
                    # check songs
                    songs = s.get_songs(first)
                    print(f"    first result '{first.name}': {len(songs)} songs")
            except Exception as e:
                print(f"  search('{artist}') failed: {e}")
        else:
            print(f"  [{name}] does not implement search()")
            break
