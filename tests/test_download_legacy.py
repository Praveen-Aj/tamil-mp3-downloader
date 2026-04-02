"""Test the IsaiminiHQ download functionality."""

from isaimini_scraper import IsaiminiScraper
from isaimini_downloader import download_from_isaimini
from pathlib import Path

# Test with a single movie
with IsaiminiScraper() as scraper:
    print('Getting categories...')
    categories = scraper.get_categories('latest')
    if categories:
        print(f'Found {len(categories)} movies')
        # Get first movie
        movie = categories[0]
        print(f'\nTesting with: {movie["name"]}')
        
        # Get songs
        songs = scraper.get_songs(movie['url'])
        print(f'Found {len(songs)} songs')
        
        if songs:
            print('\nFirst 3 songs:')
            for s in songs[:3]:
                print(f'  - {s["name"]}: {s["url"][:60]}...')
            
            # Create test output dir
            out_dir = Path('output/test')
            out_dir.mkdir(parents=True, exist_ok=True)
            
            # Try downloading first song only for test
            print('\nTesting download of first song...')
            test_songs = [songs[0]]
            total, success, failed = download_from_isaimini(test_songs, out_dir)
            print(f'\nResult: {success}/{total} successful, {failed} failed')
    else:
        print('No categories found')
