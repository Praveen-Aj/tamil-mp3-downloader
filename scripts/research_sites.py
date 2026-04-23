"""Research script: fetch Tamil music sites and compare album listings."""
import sys
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

OUT = []

def pr(*args, **kwargs):
    line = " ".join(str(a) for a in args)
    OUT.append(line)
    print(line, **kwargs)

def fetch(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=25, allow_redirects=True)
        return r.status_code, r.text, r.url
    except Exception as e:
        return None, str(e), url


# ─────────────────────────────────────────────
# 1. MassTamilan /tamil-songs (latest)
# ─────────────────────────────────────────────
pr("=" * 70)
pr("1. MASSTAMILAN /tamil-songs")
status, html, final_url = fetch("https://www.masstamilan.dev/tamil-songs")
pr(f"   Status: {status}  |  Final URL: {final_url}")
if status == 200 and html:
    soup = BeautifulSoup(html, "html.parser")
    seen = set()
    album_links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        text = a.get_text(" ", strip=True)
        if re.search(r"-songs/?(?:$|\?|#)", href, re.I) and href not in seen and text:
            seen.add(href)
            album_links.append((text, href))
    pr(f"   Total unique -songs links: {len(album_links)}")
    for t, h in album_links[:20]:
        pr(f"   [{t}] -> {h}")
else:
    pr(f"   FAILED: {html[:200] if html else 'no content'}")

# ─────────────────────────────────────────────
# 2. MassTamilan 2026 year-specific URL
# ─────────────────────────────────────────────
pr()
pr("=" * 70)
pr("2. MASSTAMILAN 2026 year-specific URL candidates")
for candidate in [
    "https://www.masstamilan.dev/2026-tamil-songs",
    "https://www.masstamilan.dev/tamil-songs?year=2026",
    "https://www.masstamilan.dev/tamil-songs/2026",
]:
    s, h, fu = fetch(candidate)
    if s is None:
        pr(f"   {candidate}  -> ERROR: {h[:80]}")
    else:
        pr(f"   {candidate}  -> {s}  final={fu}")
        if s == 200 and h:
            soup2 = BeautifulSoup(h, "html.parser")
            al = []
            seen2 = set()
            for a in soup2.find_all("a", href=True):
                href = a["href"].strip()
                text = a.get_text(" ", strip=True)
                if re.search(r"-songs/?(?:$|\?|#)", href, re.I) and href not in seen2 and text:
                    seen2.add(href)
                    al.append((text, href))
            pr(f"     album-links found: {len(al)}")
            for t, h2 in al[:5]:
                pr(f"     [{t}] -> {h2}")

# ─────────────────────────────────────────────
# 3. FriendsTamilMP3 New Releases
# ─────────────────────────────────────────────
pr()
pr("=" * 70)
pr("3. FRIENDSTAMILMP3 New Releases")
status3, html3, fu3 = fetch("https://www.friendstamilmp3.in/index.php?page=New%20Releases")
pr(f"   Status: {status3}  |  Final URL: {fu3}")
if status3 == 200 and html3:
    soup3 = BeautifulSoup(html3, "html.parser")
    seen3 = set()
    spage_links = []
    for a in soup3.find_all("a", href=True):
        href = a["href"]
        if "spage=" in href and href not in seen3:
            seen3.add(href)
            spage_links.append((a.get_text(" ", strip=True), href))
    pr(f"   Total spage= links: {len(spage_links)}")
    for t, h in spage_links[:15]:
        pr(f"   [{t}] -> {h}")
else:
    pr(f"   FAILED: {html3[:200] if html3 else 'no content'}")

# ─────────────────────────────────────────────
# 4. FriendsTamilMP3 A-Z / letter A
# ─────────────────────────────────────────────
pr()
pr("=" * 70)
pr("4. FRIENDSTAMILMP3 A-Z / letter A")
status4, html4, fu4 = fetch(
    "https://www.friendstamilmp3.in/index.php?page=A-Z%20Movie%20Songs&cpage=A"
)
pr(f"   Status: {status4}  |  Final URL: {fu4}")
if status4 == 200 and html4:
    soup4 = BeautifulSoup(html4, "html.parser")
    seen4 = set()
    spage4 = []
    for a in soup4.find_all("a", href=True):
        href = a["href"]
        if "spage=" in href and href not in seen4:
            seen4.add(href)
            spage4.append((a.get_text(" ", strip=True), href))
    pr(f"   Total spage= links: {len(spage4)}")
    year_re = re.compile(r"(19|20)\d{2}")
    with_year = [(t, h) for t, h in spage4 if year_re.search(t) or year_re.search(h)]
    without_year = [(t, h) for t, h in spage4 if not (year_re.search(t) or year_re.search(h))]
    pct = round(100 * len(with_year) / len(spage4)) if spage4 else 0
    pr(f"   With year: {len(with_year)}  Without year: {len(without_year)}  ({pct}% have detectable year)")
    pr("   --- 10 WITH year ---")
    for t, h in with_year[:10]:
        pr(f"   [{t}] -> {h}")
    pr("   --- 10 WITHOUT year ---")
    for t, h in without_year[:10]:
        pr(f"   [{t}] -> {h}")
else:
    pr(f"   FAILED: {html4[:200] if html4 else 'no content'}")

# ─────────────────────────────────────────────
# 5. IsaiminiHQ homepage
# ─────────────────────────────────────────────
pr()
pr("=" * 70)
pr("5. ISAIMINIHQ homepage")
status5, html5, fu5 = fetch("https://www.isaiminihq.com/")
pr(f"   Status: {status5}  |  Final URL: {fu5}")
if status5 == 200 and html5:
    soup5 = BeautifulSoup(html5, "html.parser")
    seen5 = set()
    hp_links = []
    for a in soup5.find_all("a", href=True):
        href = a["href"]
        if "-songs" in href and href not in seen5:
            seen5.add(href)
            hp_links.append((a.get_text(" ", strip=True), href))
    pr(f"   Total -songs links: {len(hp_links)}")
    for t, h in hp_links[:15]:
        pr(f"   [{t}] -> {h}")
else:
    pr(f"   FAILED: {html5[:200] if html5 else 'no content'}")
    html5 = ""

# ─────────────────────────────────────────────
# 6. IsaiminiHQ 2026
# ─────────────────────────────────────────────
pr()
pr("=" * 70)
pr("6. ISAIMINIHQ 2026 year page")
status6, html6, fu6 = fetch("https://www.isaiminihq.com/2026-tamil-mp3-songs/")
pr(f"   Status: {status6}  |  Final URL: {fu6}")
yr2026_links = []
if status6 == 200 and html6:
    soup6 = BeautifulSoup(html6, "html.parser")
    seen6 = set()
    for a in soup6.find_all("a", href=True):
        href = a["href"]
        if "-songs" in href and href not in seen6:
            seen6.add(href)
            yr2026_links.append((a.get_text(" ", strip=True), href))
    pr(f"   Total -songs links: {len(yr2026_links)}")
    for t, h in yr2026_links[:15]:
        pr(f"   [{t}] -> {h}")
else:
    pr(f"   FAILED/redirect: {html6[:200] if html6 else 'no content'}")

# ─────────────────────────────────────────────
# 7. IsaiminiHQ 2025
# ─────────────────────────────────────────────
pr()
pr("=" * 70)
pr("7. ISAIMINIHQ 2025 year page")
status7, html7, fu7 = fetch("https://www.isaiminihq.com/2025-tamil-mp3-songs/")
pr(f"   Status: {status7}  |  Final URL: {fu7}")
yr2025_links = []
if status7 == 200 and html7:
    soup7 = BeautifulSoup(html7, "html.parser")
    seen7 = set()
    for a in soup7.find_all("a", href=True):
        href = a["href"]
        if "-songs" in href and href not in seen7:
            seen7.add(href)
            yr2025_links.append((a.get_text(" ", strip=True), href))
    pr(f"   Total -songs links: {len(yr2025_links)}")
    for t, h in yr2025_links[:15]:
        pr(f"   [{t}] -> {h}")
else:
    pr(f"   FAILED/redirect: {html7[:200] if html7 else 'no content'}")

# ─────────────────────────────────────────────
# Comparison: IsaiminiHQ homepage vs 2026 vs 2025
# ─────────────────────────────────────────────
pr()
pr("=" * 70)
pr("COMPARISON: IsaiminiHQ homepage vs 2026 vs 2025")

hp_hrefs  = {h for _, h in hp_links}  if "hp_links"  in dir() else set()
y26_hrefs = {h for _, h in yr2026_links}
y25_hrefs = {h for _, h in yr2025_links}

pr(f"  Homepage  total album hrefs: {len(hp_hrefs)}")
pr(f"  2026 page total album hrefs: {len(y26_hrefs)}")
pr(f"  2025 page total album hrefs: {len(y25_hrefs)}")

overlap_hp_26  = hp_hrefs & y26_hrefs
overlap_hp_25  = hp_hrefs & y25_hrefs
overlap_26_25  = y26_hrefs & y25_hrefs

pr(f"  HP ∩ 2026: {len(overlap_hp_26)} common links")
pr(f"  HP ∩ 2025: {len(overlap_hp_25)} common links")
pr(f"  2026 ∩ 2025: {len(overlap_26_25)} common links")

if len(y26_hrefs) > 0 and len(y25_hrefs) > 0:
    if overlap_26_25 == y26_hrefs:
        pr("  => 2026 and 2025 pages are IDENTICAL content")
    elif len(overlap_26_25) > min(len(y26_hrefs), len(y25_hrefs)) * 0.8:
        pr("  => 2026 and 2025 pages are MOSTLY SAME (>80% overlap)")
    else:
        pr("  => 2026 and 2025 pages are DIFFERENT content")

# write to file too
with open("logs/research_results.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(OUT))
print("\nResults saved to logs/research_results.txt")
