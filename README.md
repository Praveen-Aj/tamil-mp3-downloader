# Tamil MP3 Downloader v3.0.0

Modular Tamil MP3 downloader with GUI/TUI clients, multi-source scraping, and concurrent downloads.

## Current Status

- Active version: `3.0.0`
- Primary runtime: `gui.py`
- Optional terminal UI: `tui.py`
- `main.py` is now a compatibility shim that forwards to GUI startup.

## Quick Start

```bash
git clone https://github.com/anburocky3/tamil-mp3-downloader.git
cd tamil-mp3-downloader
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python gui.py
```

## Features Available In This Version

- Multi-source scraping: IsaiminiHQ, MassTamilan, FriendsTamilMP3
- Category and album browsing
- Search flow across sources
- Concurrent and resumable downloads (`.part` + `.download_state.json`)
- ID3 tagging via `mutagen`
- Persistent settings in `config/settings.json`
- Windows EXE packaging via PyInstaller spec in `scripts/`

## Project Structure

```text
tamil-mp3-downloader/
|-- gui.py
|-- tui.py
|-- main.py
|-- config/
|-- data/
|-- docs/
|-- downloaders/
|-- models/
|-- scrapers/
|-- scripts/
|-- tests/
`-- utils/
```

## Running Options

- GUI (recommended): `python gui.py`
- TUI: `python tui.py`
- Compatibility launcher: `python main.py`

## Build EXE (Windows)

See `docs/DOWNLOAD.md` for full steps.

Quick command:

```cmd
.venv\Scripts\python.exe -m PyInstaller scripts\tamil_mp3_downloader.spec --clean
```

## Testing

Targeted scraper test currently used in this release line:

```bash
pytest tests/test_masstamilan_scraper.py -q
```

Note: network-facing scraper tests can be skipped/fail depending on upstream site behavior.

## Documentation

- Architecture: `ARCHITECTURE.md`
- Roadmap and status: `ROADMAP.md`
- Build/download guide: `docs/DOWNLOAD.md`
- Contribution guide: `docs/CONTRIBUTING.md`

## License

MIT. See `LICENSE`.
