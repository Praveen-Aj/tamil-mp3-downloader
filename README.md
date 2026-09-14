# Tamil MP3 Downloader v4.0.0

A powerful, library-centric desktop application for discovering, deduplicating, and downloading Tamil music from multiple sources.

## Current Status

- **Active Version:** `4.0.0`
- **Architecture:** SQLite Canonical Library & CustomTkinter UI
- **Primary Runtime:** `main.py` (via `launch_app.bat` on Windows)

## What's New in v4 (Library-Centric Redesign)

The v4 release fundamentally changes the application from a "search-and-download" scraper tool into a **Music Library Manager**.

- **Canonical SQLite Library:** Songs discovered from different websites (e.g., MassTamilan, Tamilmp3) are analyzed, deduplicated, and stored locally.
- **Source Health Registry:** The application continuously monitors scraping sources for uptime and automatically shifts to fallback domains when a site goes offline.
- **Deduplication:** A song found in multiple categories or on multiple websites is collapsed into a single Library entity with multiple source choices.
- **Download Planner:** Automatically upgrades selected songs to higher qualities (e.g., 320kbps) if a better variant exists in the library.
- **10,000+ Song Performance:** Uses database pagination and background threading to ensure the UI remains smooth regardless of library size.
- **Local MP3 Import:** Scan your existing local files and integrate them into the canonical library to prevent re-downloading songs you already own.

## Quick Start

```bash
git clone https://github.com/Praveen-Aj/tamil-mp3-downloader.git
cd tamil-mp3-downloader
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

To run the application:
Double-click `launch_app.bat` or run `python main.py`.

## Project Structure

```text
tamil-mp3-downloader/
|-- main.py              # Application entry point
|-- launch_app.bat       # Windows batch launcher
|-- config/              # User settings (settings.json)
|-- docs/                # Project documentation and architecture guide
|-- downloaders/         # Concurrent HTTP download logic
|-- library/             # SQLite library backend and database schemas
|-- models/              # Dataclasses and core models
|-- scrapers/            # Source-specific HTML scrapers
|-- scripts/             # Build scripts
|-- tests/               # Pytest suite
|-- ui/                  # CustomTkinter Modular UI 
`-- utils/               # Shared utilities
```

## Build EXE (Windows)

See `docs/DOWNLOAD.md` for full steps.

Quick command:

```cmd
scripts\build_exe.bat
```

## Testing

Run the local, mocked test suite (fast and offline):

```bash
pytest tests/ -v
```

Run the live scraper protocol test suite (requires internet connection):

```bash
pytest tests/ -m live -v
```

## Documentation

- **Architecture Blueprint:** `docs/architecture.md`
- Build/download guide: `docs/DOWNLOAD.md`
- Contribution guide: `docs/CONTRIBUTING.md`

## License

MIT. See `LICENSE`.
