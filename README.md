# Tamil MP3 Downloader v4.1.0

A modern, library-centric desktop application for acquiring, organizing, and managing music collections via Universal URLs (Spotify, YouTube, Regional sources) with canonical deduplication and automatic tagging.

> [!CAUTION]
> **LEGAL & USAGE DISCLAIMER**  
> This project is an open-source **Audio Library Management & Acquisition System** developed for personal archival, educational, and backup purposes. Users are solely responsible for ensuring that all content acquired complies with applicable copyright laws, licensing terms, and third-party platform agreements. The authors do not host, distribute, or condone the infringement of copyrighted material.

## Current Status

- **Active Version:** `4.1.0`
- **Architecture:** Canonical SQLite Engine, Pluggable Audio Providers, and Modern CustomTkinter UI
- **Primary Runtime:** `main.py` (via `launch_app.bat` on Windows)

## Key Features

- **Universal Music URL Import:** Paste links from Spotify (playlists, albums, tracks), YouTube, YouTube Music, Tamil regional sources, or direct audio streams.
- **Audio Provider Abstraction & Matching:** Uses `TrackMatcher` to find and score the closest matching audio stream across multiple providers with fuzzy title and duration similarity.
- **Persistent Resumable Playlist Jobs:** Multi-track playlist downloads survive application restarts and allow single-click retries of failed tracks.
- **Canonical SQLite Library:** Central database automatically deduplicates tracks, tracks owned files, and prevents duplicate downloads.
- **Automatic ID3v2.3 Tagging:** Embeds Title, Artist, Album, Year, Track Number, and Cover Artwork directly into downloaded audio files.
- **Local Library Import:** Existing MP3 directories can be scanned into the canonical library as `OWNED` via `Library → Import Existing Files`.

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
