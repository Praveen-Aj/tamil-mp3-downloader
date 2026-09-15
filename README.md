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

- **Filesystem as Single Source of Truth:** A song is marked as downloaded if and only if a real, valid audio file exists on disk. No synthetic or fabricated metrics.
- **Universal Music URL Import:** Paste links from Spotify (playlists, albums, tracks), YouTube, YouTube Music, Tamil regional sources, or direct audio streams into the centerpiece Add Music view.
- **Dedicated Downloaded Songs View:** Browse your offline collection, play audio, open folder in Windows Explorer, or perform dual-mode deletion (Delete from Disk vs. Remove from Library).
- **Automatic Fallback & Bounded Retry:** Automatically tries alternative providers if the primary source fails (HTTP 404/unavailable) with exponential backoff on transient errors.
- **Interactive Playlist Results UI:** Review analyzed playlists with track selection checkboxes, status filter dropdowns, and batch one-click downloading.
- **Full Desktop Download Manager:** Live aggregate queue progress, transfer speeds, ETA timers, and file explorer actions.
- **Audio Provider Abstraction & Matching:** Uses `TrackMatcher` to find and score the closest matching audio stream across multiple providers with fuzzy title and duration similarity.
- **Automatic ID3v2.3 Tagging:** Embeds Title, Artist, Album, Year, Track Number, and Cover Artwork directly into downloaded audio files.
- **Modern Dark Design System:** Curated obsidian/navy aesthetic with semantic indicators, categorized navigation, and live notification badge pills.

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

## Testing

Run the multi-tier test suite (fast, deterministic, uses local HTTP audio streams):

```bash
pytest -v
```

Run opt-in live network tests (requires active internet connection):

```bash
pytest -m live -v
```

## Documentation

- **Architecture Blueprint:** `docs/architecture.md`
- Build/download guide: `docs/DOWNLOAD.md`
- Contribution guide: `docs/CONTRIBUTING.md`

## License

MIT. See `LICENSE`.
