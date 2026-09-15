# Tamil MP3 Downloader: End-User Guide (v4.2.0)

## 1. Introduction

Tamil MP3 Downloader is a modern desktop music acquisition platform and canonical offline music library manager. Built on a rich dark obsidian design system, it delivers an effortless, single-goal workflow:

```text
"I want to download a song."
```

The application handles all matching, provider resolution, quality upgrades, and retry fallbacks automatically without requiring technical decision-making or manual review.

---

## 2. Centerpiece Acquisition: Add Music via URL or Search

1. In the sidebar, select **⚡ Add Music** (the centerpiece of the application).
2. Paste any song, album, or playlist URL in the input bar:
   * **Spotify**: `https://open.spotify.com/playlist/...` or `https://open.spotify.com/track/...`
   * **YouTube / YouTube Music**: `https://www.youtube.com/playlist?list=...` or `watch?v=...`
   * **Regional Tamil Sites**: MassTamilan, TamilMP3, FriendsTamilMP3, etc.
   * **Direct Audio Links**: Any direct link ending in `.mp3`, `.m4a`, or `.wav`.
3. Click **⚡ Analyze URL**.
4. The system automatically inspects the link, fetches track metadata, identifies candidate audio streams, and presents the playlist summary.
5. Click **📥 Download Selected Tracks** (or download individual tracks).
6. The application transparently attempts the highest-bitrate provider, validates the downloaded audio bytes, tags the MP3 with ID3 metadata and album art, and registers the file in your local library.

---

## 3. Dedicated Downloaded Songs Manager

Click **🎵 Downloaded Songs** in the sidebar to browse and manage your physical offline music library:

* **Real Filesystem Verification**: Only songs with verified, non-zero audio files present on disk are displayed. If a file is moved or deleted externally, the library automatically reconciles its status.
* **Inline Actions**:
  * **▶ Play**: Plays the local audio file using your default system audio player.
  * **📁 Open Folder**: Immediately reveals and highlights the physical MP3 in Windows Explorer.
  * **🗑️ Delete Options**:
    * **Delete File**: Permanently deletes the audio file from your hard drive, removes download history, and resets the track state to `NEW`.
    * **Remove from Library**: Removes database tracking records while preserving the physical MP3 file on disk.

---

## 4. Modern Downloads Queue

Click **📥 Downloads** in the sidebar to monitor active transfers:

* **Real-Time Transfer Metrics**: Displays live transfer rate (MB/s), ETA, and overall queue completion count.
* **Control Actions**:
  * `⏸ Pause` / `▶ Resume`: Control individual background transfers.
  * `🔄 Retry`: Re-attempts failed downloads with automatic fallback to alternate audio providers.
  * `📁 Open Folder`: Opens the destination folder once the download completes.

---

## 5. Library Catalog & Offline Folder Import

* **Canonical Deduplication**: Every song has a canonical identity. If you already own a song at 320 kbps, the downloader automatically skips it to save bandwidth and prevent duplicate files.
* **Importing Existing Music**:
  1. Open **📚 Library**.
  2. Click **📂 Import Existing Files**.
  3. Select any local folder containing MP3 files.
  4. The scanner indexes all ID3 tags into the local SQLite database and marks the files as `OWNED`.

---

## 6. Categorized Settings Center

Configure application behavior under **⚙️ Settings**:
* **GENERAL**: Choose your preferred download directory and toggle confirmation prompts for large playlist batches.
* **DOWNLOADS**: Configure concurrent download workers (1–8) and preferred audio quality (320 kbps / 128 kbps).
* **METADATA**: Toggle automatic ID3v2.3 tagging and cover artwork embedding.
* **LIBRARY**: Manage deduplication rules, automatic quality upgrades, and filesystem integrity reconciliation.
* **SOURCES**: Configure enabled scraper sources and streaming providers.
