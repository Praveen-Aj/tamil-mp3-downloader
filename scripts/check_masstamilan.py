import cloudscraper
from bs4 import BeautifulSoup

scr = cloudscraper.create_scraper()
url = 'https://www.masstamilan.dev/tamil-songs'
resp = scr.get(url, timeout=30)
print('status', resp.status_code)
print('final_url', resp.url)

soup = BeautifulSoup(resp.text, 'html.parser')
print('title', soup.title.string if soup.title else 'NO')
items = soup.select('div.listing-page .list_item a')
print('items', len(items))
for i, a in enumerate(items[:7]):
    print(i, a.get('href'), a.text.strip())
