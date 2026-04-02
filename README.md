# Tamil MP3 Downloader v3.0
<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-blue"  alt="Platform"/>
  <img src="https://img.shields.io/badge/Python-3.10%2B-brightgreen" alt="python 3.10"/>
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="mit-license" />
  <img src="https://img.shields.io/github/last-commit/anburocky3/tamil-mp3-downloader/main?label=Last%20updated%20on" alt="Last updated on" />
</p>

A modern, modular Tamil MP3 downloader with multiple sources and clean architecture. 🎵

## ✨ What's New in v3.0

- **🔄 Complete Architecture Rewrite** - Modern, maintainable codebase
- **🌐 Multiple Sources** - IsaiminiHQ (latest 2024-2025) + more coming
- **🎯 Production Ready** - Proper error handling, logging, and testing
- **📦 Modular Design** - Clean separation of concerns
- **⚡ Fast Downloads** - Progress bars and concurrent downloads
- **🔧 Easy Configuration** - JSON-based settings

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/anburocky3/tamil-mp3-downloader.git
cd tamil-mp3-downloader

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install
```

### Run

```bash
python main.py
```

## 📋 Features

### ✅ Current Features
- **IsaiminiHQ Integration** - Latest Tamil movies (2024-2025)
- **Interactive CLI** - User-friendly menu system
- **Progress Tracking** - Real-time download progress with tqdm
- **Error Handling** - Robust error recovery and logging
- **Organized Output** - Files saved by source/movie
- **Batch Downloads** - Download multiple albums at once

### 🔄 Coming Soon
- **FriendsTamilMP3** - Classic songs (2010-2015)
- **Settings Menu** - Configurable preferences
- **Resume Downloads** - Interrupted download recovery
- **Search Functionality** - Find songs across sources
- **Metadata Tagging** - ID3 tags for MP3s

## 🏗️ Architecture

```
tamil-mp3-downloader/
├── main.py                    # Entry point - clean CLI
├── scrapers/                  # Source-specific scrapers
│   ├── base.py               # Abstract scraper interface
│   └── isaimini.py           # IsaiminiHQ implementation
├── downloaders/               # Download management
│   ├── base.py               # Abstract downloader
│   └── http_downloader.py    # HTTP downloads with progress
├── models/                    # Data models
│   └── song.py               # Song, Album dataclasses
├── utils/                     # Utilities
│   └── logger.py             # Logging setup
├── config/                    # Configuration
│   └── settings.py           # App settings
├── data/                      # Static data files
├── output/                    # Download directory
└── logs/                      # Application logs
```

## 🎵 Usage

1. **Start the application:**
   ```bash
   python main.py
   ```

2. **Select a source:**
   ```
   Select Source:
   1. IsaiminiHQ (Latest 2024-2025) ⭐
   2. FriendsTamilMP3 (Classics)
   3. Settings
   4. Exit
   ```

3. **Choose albums to download:**
   - View available movies/albums
   - Select by number, range, or 'all'
   - Example: `1,3,5` or `2-4` or `all`

4. **Confirm and download:**
   - Review selected songs
   - Confirm download
   - Watch progress bars
   - Files saved to `output/` directory

## 🔧 Configuration

Settings are stored in `config/settings.json`. Default settings:

```json
{
  "sources": {
    "isaimini": {
      "base_url": "https://www.isaiminihq.com",
      "enabled": true
    }
  },
  "download": {
    "output_dir": "output",
    "chunk_size": 8192,
    "timeout": 60
  },
  "ui": {
    "page_size": 10,
    "show_progress": true
  }
}
```

## 🧪 Testing

Run the test suite:

```bash
python test_new_architecture.py
```

This validates:
- ✅ Scraper connectivity
- ✅ Album discovery
- ✅ Song extraction
- ✅ Downloader initialization

## 📦 Dependencies

- `playwright>=1.40.0` - Browser automation for JavaScript sites
- `requests>=2.28.0` - HTTP requests
- `beautifulsoup4>=4.11.0` - HTML parsing
- `colorama>=0.4.5` - Cross-platform colored output
- `tqdm>=4.64.0` - Progress bars
- `pydantic>=2.0.0` - Data validation

## ⚠️ Disclaimer

> **Use this script with caution.** We don't support piracy and this project is completely for educational purposes only. Use it with care.🥰💖

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

## 🤝 Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## 📞 Support

- Create an [issue](https://github.com/anburocky3/tamil-mp3-downloader/issues) for bugs
- Star the repo if you find it useful ⭐
- Fork and contribute improvements!

![Screenshot 6](/screenshots/6.png)

7. Download specific album songs or all songs from the selections.

![Screenshot 7](/screenshots/7.png)

8. Check the output folder, all the songs will be downloaded here.

![Screenshot 8](/screenshots/8.png)

### Get started 

1. [Fork this repository](https://github.com/anburocky3/tamil-mp3-downloader/fork) and clone it to your local machine:
```bash
   # replace yourName with your GitHub username
   git clone https://github.com/yourName/tamil-mp3-downloader.git
   cd tamil-mp3-downloader
```
2. Make sure you have [Python 3.10+](https://www.python.org/downloads/) installed. You can check by running:

```bash
   python --version
   pip install -r requirements.txt
```

3. Run the app:

```bash
   python main.py
```

> Or download a ready-to-run Windows EXE from the Releases page (see [`DOWNLOAD.md`](./DOWNLOAD.md)).


### Where files go

- Files are saved to:

  `output/<CategoryName>/<AlbumName>/` 📂


License

- [MIT](./LICENSE)


### Contribute / Help

- Contribution guidelines, reporting issues, and PR steps live in [`CONTRIBUTING.md`](./CONTRIBUTING.md) — please read before sending changes. 🙏



### Author:
- [Anbuselvan Rocky](https://fb.me/anburocky3)
