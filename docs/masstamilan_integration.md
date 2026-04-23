# MassTamilan Integration

This project now supports two sources:

- `IsaiminiHQ` (stable, full ZIP + MP3 links for older and some newer movies)
- `MassTamilan` (latest releases, but may require Cloudflare challenge bypass)

## Behavior

- MassTamilan is selected from main menu as `MassTamilan`.
- It uses `cloudscraper` for initial page fetch.
- If cloudflare JS content is needed, it falls back to Playwright rendering.
- Page content is dynamic; if no album appears, fallback to Isaimini is recommended.

## How to run

- `pip install -r requirements.txt`
- `python gui.py`

## Notes

- MassTamilan may need `playwright install chromium` (already done in this environment).
- Albums from MassTamilan can be shuffled by categories and will be cached on each run.
