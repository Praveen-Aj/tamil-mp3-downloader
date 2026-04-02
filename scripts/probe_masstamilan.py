"""
Probe MassTamilan.dev download URL structure via cloudscraper + BeautifulSoup.
"""
import re
import cloudscraper
from bs4 import BeautifulSoup

ALBUM_URL = "https://www.masstamilan.dev/karuppu-2026-songs"
LATEST_URL = "https://www.masstamilan.dev/tamil-songs"

scraper = cloudscraper.create_scraper()

print("=== Probing album page ===")
resp = scraper.get(ALBUM_URL, timeout=30)
print(f"Status: {resp.status_code}")
soup = BeautifulSoup(resp.text, "html.parser")
print(f"Title: {soup.title.string if soup.title else 'N/A'}")

# All links
dl_links = soup.find_all("a", href=re.compile(r"downloader|\.mp3|\.zip", re.I))
print(f"\nDownload links: {len(dl_links)}")
for a in dl_links:
    print(f"  [{a.get_text(strip=True)[:60]}]\n    → {a['href'][:120]}")

# Song table
rows = soup.select("table tr")
print(f"\nTable rows: {len(rows)}")
for row in rows:
    cells = row.find_all(["th","td"])
    if cells:
        texts = [c.get_text(strip=True)[:40] for c in cells]
        links = [(a.get_text(strip=True), a['href']) for a in row.find_all('a', href=True)]
        print(f"  {texts}")
        for lt, lh in links:
            print(f"    link: [{lt}] → {lh[:100]}")

print("\n\n=== Probing latest releases page ===")
resp2 = scraper.get(LATEST_URL, timeout=30)
print(f"Status: {resp2.status_code}")
soup2 = BeautifulSoup(resp2.text, "html.parser")

album_links = soup2.find_all("a", href=re.compile(r"-songs", re.I))
seen = set()
print(f"Album links (unique):")
for a in album_links:
    h = a.get("href","")
    if h and h not in seen and not h.startswith("?"):
        seen.add(h)
        txt = a.get_text(strip=True)[:50]
        if txt:
            print(f"  [{txt}] → {h[:80]}")

ALBUM_URL = "https://www.masstamilan.dev/karuppu-2026-songs"
LATEST_URL = "https://www.masstamilan.dev/tamil-songs"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.masstamilan.dev/",
}

print("=== Probing album page ===")
resp = requests.get(ALBUM_URL, headers=HEADERS, timeout=30)
print(f"Status: {resp.status_code}")
print(f"Title: {resp.text[resp.text.find('<title>')+7:resp.text.find('</title>')][:80]}")

soup = BeautifulSoup(resp.text, "html.parser")

# All links with 'downloader' in href
dl_links = soup.find_all("a", href=re.compile(r"downloader|\.mp3|\.zip", re.I))
print(f"\nDownload links found: {len(dl_links)}")
for a in dl_links:
    print(f"  [{a.get_text(strip=True)[:60]}] → {a['href'][:100]}")

# Song table rows
rows = soup.select("table tr")
print(f"\nTable rows: {len(rows)}")
for row in rows[:5]:
    print(f"  {row.get_text(separator='|', strip=True)[:120]}")

print("\n\n=== Probing latest page ===")
resp2 = requests.get(LATEST_URL, headers=HEADERS, timeout=30)
print(f"Status: {resp2.status_code}")
soup2 = BeautifulSoup(resp2.text, "html.parser")

# Find album links
album_links = soup2.find_all("a", href=re.compile(r"-20\d\d-songs|-songs", re.I))
print(f"Album links found: {len(album_links)}")
for a in album_links[:15]:
    print(f"  [{a.get_text(strip=True)[:50]}] → {a['href'][:80]}")

from playwright.sync_api import sync_playwright

ALBUM_URL = "https://www.masstamilan.dev/karuppu-2026-songs"

JS_PROBE = r"""
() => {
    const results = { links: [], forms: [], scripts: [] };

    // All <a> with download-looking href
    document.querySelectorAll('a[href]').forEach(a => {
        const h = (a.getAttribute('href') || '');
        const t = (a.textContent || '').trim().substring(0, 80);
        if (h.includes('downloader') || h.includes('.mp3') || h.includes('.zip')
            || h.includes('download') || /\d+kbps/i.test(t) || /mb\)/i.test(t)) {
            results.links.push({ text: t, href: h });
        }
    });

    // Buttons with onclick or data attributes that might trigger download
    document.querySelectorAll('button[onclick], button[data-url], button[data-href], a[data-url]').forEach(el => {
        results.forms.push({
            tag: el.tagName,
            text: (el.textContent || '').trim().substring(0, 60),
            onclick: el.getAttribute('onclick') || '',
            dataUrl: el.getAttribute('data-url') || el.getAttribute('data-href') || ''
        });
    });

    return results;
}
"""

with sync_playwright() as p:
    br = p.chromium.launch(headless=True)
    page = br.new_page()
    print(f"Loading: {ALBUM_URL}")
    page.goto(ALBUM_URL, wait_until="domcontentloaded", timeout=60000)
    page.wait_for_timeout(5000)

    data = page.evaluate(JS_PROBE)

    print(f"\n=== Download Links ({len(data['links'])}) ===")
    for lnk in data['links']:
        print(f"  [{lnk['text']}]\n    → {lnk['href']}\n")

    print(f"\n=== Interactive Buttons ({len(data['forms'])}) ===")
    for btn in data['forms']:
        print(f"  [{btn['tag']}] {btn['text']}")
        if btn['onclick']:
            print(f"    onclick: {btn['onclick'][:120]}")
        if btn['dataUrl']:
            print(f"    data-url: {btn['dataUrl'][:120]}")

    # Also dump ALL hrefs to see what's on the page at all
    all_hrefs = page.evaluate(r"() => Array.from(document.querySelectorAll('a[href]')).map(a => ({t: a.textContent.trim().substring(0,50), h: a.getAttribute('href').substring(0,100)}))")
    print(f"\n=== All hrefs on page ({len(all_hrefs)}) ===")
    for h in all_hrefs[:30]:
        print(f"  [{h['t']}] → {h['h']}")

    # Raw page title/body snippet
    title = page.title()
    body_text = page.inner_text('body')[:500] if page.query_selector('body') else ''
    print(f"\nPage title: {title}")
    print(f"Body snippet: {body_text[:300]}")

    br.close()
