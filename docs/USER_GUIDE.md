# Tamil MP3 Downloader: End-User Guide

## 1. Introduction

Tamil MP3 Downloader is a modern desktop music acquisition tool and local canonical music library manager. It allows you to paste music links from Spotify, YouTube, or regional music sites, review matched audio tracks, and download high-quality, tagged audio files directly to your storage.

---

## 2. Adding Music via URL

1. In the sidebar, select **➕ Add Music**.
2. Paste any supported song, album, or playlist URL in the input bar:
   * **Spotify**: `https://open.spotify.com/playlist/...` or `track/...`
   * **YouTube**: `https://www.youtube.com/playlist?list=...` or `watch?v=...`
   * **YouTube Music**: `https://music.youtube.com/...`
   * **Regional Tamil Sites**: MassTamilan, TamilMP3, etc.
   * **Direct Audio**: Any direct link ending in `.mp3` or `.m4a`
3. Click **⚡ Analyze URL**.
4. The application analyzes the link, extracts canonical track metadata, checks your local library for existing tracks, and evaluates audio source candidates.
5. Click **📥 Download Ready Tracks** to start acquiring your music.

---

## 3. Reviewing Track Matches

In the Analysis table, each track displays:
* **Track Title & Artist**
* **Duration**
* **Audio Source**: The candidate provider (e.g. YouTube, Tamil Regional, Direct HTTP).
* **Confidence**: A percentage score indicating how closely the candidate title and duration match the requested track.
* **Status**:
  * `OWNED`: Already exists in your local library at equal or higher quality (will not be re-downloaded).
  * `READY`: High-confidence audio source identified, ready for batch download.
  * `NEEDS REVIEW`: Medium-confidence match; user review suggested.
  * `NO SOURCE`: No matching audio stream found.
  * `FAILED`: Download error during execution (can be retried with one click).

---

## 4. Monitoring the Download Queue

Click **📥 Downloads Queue** in the sidebar:
* Track live download progress, transfer speeds, and completion percentages.
* **Pause / Resume**: Control active transfers.
* **Retry Failed**: Automatically re-attempts only failed tracks without re-downloading completed songs.

---

## 5. Importing Existing Music Folders

If you already have MP3s on your computer:
1. Navigate to **📚 Library**.
2. Click **📂 Import Existing Files** in the action bar.
3. Select your local music directory.
4. The scanner extracts ID3 tags, registers files into the SQLite database, and sets their status to `OWNED`.
5. Future URL/playlist downloads will automatically detect these tracks as owned, avoiding duplicates.

---

## 6. Audio Tagging & Organization

All successfully downloaded audio tracks are tagged with ID3v2.3 metadata:
* Track Title
* Contributing Artist
* Album Name
* Track Number
* Release Year
* Embedded Front Cover Art
