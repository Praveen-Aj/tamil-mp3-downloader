# Tamil MP3 Downloader: End-User Guide (v4.1.0)

## 1. Introduction

Tamil MP3 Downloader is a modern desktop music acquisition tool and local canonical music library manager. It features a complete visual redesign built on a rich dark obsidian palette, categorized navigation, and a consumer-friendly workflow:

```text
Paste URL / Playlist  →  Analyze  →  Review & Select Tracks  →  Download  →  Organize into Library
```

---

## 2. Centerpiece Acquisition: Add Music via URL

1. In the sidebar, select **⚡ Add Music** (the visual centerpiece of the application).
2. Paste any supported song, album, or playlist URL in the input bar:
   * **Spotify**: `https://open.spotify.com/playlist/...` or `track/...`
   * **YouTube**: `https://www.youtube.com/playlist?list=...` or `watch?v=...`
   * **YouTube Music**: `https://music.youtube.com/...`
   * **Regional Tamil Sites**: MassTamilan, TamilMP3, etc.
   * **Direct Audio**: Any direct link ending in `.mp3`, `.m4a`, or `.wav`
3. Click **⚡ Analyze URL**.
4. The system detects the platform, fetches canonical metadata, and queries audio providers for the best match.

---

## 3. Interactive Playlist Result UI

When a playlist or multi-track link is analyzed, the app presents a rich track selection interface:
* **Playlist Summary Header**: Displays playlist name, content type, track count, owned count, ready count, and unavailable count.
* **Selection Toolbar**:
  * `Select All`: Check all tracks for download.
  * `Select None`: Clear all checkboxes.
  * `Invert`: Reverse current checkbox selection.
  * **Search Filter**: Real-time filter by track title or artist.
  * **Status Filter Dropdown**: Filter by `All Tracks`, `Ready to Download`, `Needs Review`, `Already Owned`, or `Unavailable`.
* **Track Cards**:
  * Checkbox to toggle individual tracks.
  * Track number, Title, Artist, Duration.
  * Audio source provider badge (YouTube, Regional Scrapers, Direct).
  * Match confidence percentage chip (e.g. `96% match`).
  * Status pill: `✓ Already in Library`, `↓ Ready to Download`, `⚠ Review Match`, `✕ Unavailable`.
* **Sticky Action Footer**:
  * Live selection counter: `"Selected: 23 of 42 tracks"`.
  * Prominent action button: **[ 📥 Download Selected Tracks ]**.

---

## 4. Modern Downloads Manager Queue

Click **📥 Downloads** in the sidebar:
* **Aggregate Progress Banner**: Shows overall queue completion (`45 of 87 completed`), current speed (`2.4 MB/s`), and ETA.
* **Filter Tabs**: View `All`, `Active`, `Queued`, `Completed`, or `Failed` tasks.
* **Track Download Cards**:
  * Artwork placeholder thumbnail.
  * Title, Artist, Source badge.
  * Percentage progress bar.
  * Metrics: Live transfer speed, estimated time remaining.
  * Contextual Actions: `⏸ Pause`, `▶ Resume`, `🔄 Retry`, `📁 Open Folder` (reveals MP3 file in Windows Explorer).
* **Batch Controls**: `🔄 Retry Failed`, `⏸ Pause All`, `▶ Resume All`.

---

## 5. Review Results Center

Click **🎯 Review Results** in the sidebar:
* **Attention Required Mode**: Displays conflict cards for tracks that need user decision:
  * Unowned tracks with medium match confidence.
  * Duplicate candidates or potential 320 kbps quality upgrades.
  * Detailed reason pills and recommended actions (`✓ Accept & Download`, `🔍 Inspector`).
* **Discovery Table Mode**: Full paginated catalog review of regional scraping sessions with Download Plan Preview.

---

## 6. Library & Offline Folder Import

* **Canonical Deduplication**: Your collection is tracked in a local SQLite database. If a track is already owned at 320 kbps, the downloader skips it automatically to save disk space and bandwidth.
* **Quality Upgrades**: If you own a 128 kbps track and a verified 320 kbps master is found, it is flagged for an upgrade.
* **Import Existing Files**:
  1. Open **📚 Library**.
  2. Click **📂 Import Existing Files** in the action bar.
  3. Select your local music directory.
  4. The scanner indexes all ID3 tags into SQLite and marks them as `OWNED`.

---

## 7. Categorized Settings Center

Configure application behavior under **⚙️ Settings**:
* **GENERAL**: Download folder location, confirm bulk downloads (>25 tracks).
* **DOWNLOADS**: Simultaneous worker threads (1-8), preferred audio quality (320 kbps / 128 kbps).
* **METADATA**: Embed ID3v2.3 tags, download high-res album artwork, clean filename descriptors.
* **LIBRARY**: Strict deduplication policy, automatic quality upgrades.
* **SOURCES**: Enable/disable YouTube, Regional Tamil scrapers, or Direct streams.
* **ABOUT & LEGAL**: Version information and copyright compliance notice.
