from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('https://www.masstamilan.dev/tamil-songs', wait_until='networkidle', timeout=60000)
    print('title', page.title())
    html = page.content()
    print('len html', len(html))
    # try identify song cards
    cards = page.query_selector_all('div.listing-page .list_item')
    print('cards count', len(cards))
    for i, c in enumerate(cards[:5]):
        print('card', i, c.inner_text()[:120])
    browser.close()