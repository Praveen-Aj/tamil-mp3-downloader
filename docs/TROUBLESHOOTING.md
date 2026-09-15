# Troubleshooting & FAQ
 
## 1. Common Issues and Solutions

### Issue: "Song shows as NEW even though it was previously downloaded"
* **Cause**: The application maintains a strict **Filesystem Truth** invariant. If an audio file is moved, renamed, corrupted, or deleted on disk externally, the database automatically reconciles its status to `NEW`.
* **Resolution**: Keep downloaded songs in their designated library directories, or use `Library → Import Existing Files` to rescan songs stored in custom directories.

### Issue: "Download failed: File appears to be HTML or corrupted stream"
* **Cause**: Some upstream mirrors or cloud protection proxies return an HTML error or verification page with a `.mp3` extension. The downloader checks binary header signatures (MPEG sync `\xff\xfb`, ID3v2 tags, RIFF, AAC) and immediately rejects false payloads to prevent unplayable files on disk.
* **Resolution**: Click `Retry` on the download task to trigger automatic fallback to alternate audio providers.

### Issue: "yt-dlp is required to analyze YouTube URLs"
* **Cause**: The `yt-dlp` Python package is not installed in the environment.
* **Resolution**: Run `.venv\Scripts\pip install yt-dlp` in the project directory.

### Issue: "FFmpeg not detected; native container audio will be downloaded"
* **Cause**: FFmpeg executable is not present in Windows system `PATH`.
* **Impact**: Audio files from YouTube will download in their native container format (`.m4a` or `.webm`) instead of being re-encoded to `.mp3`.
* **Resolution**:
  1. Download FFmpeg essentials build from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/).
  2. Extract the archive and copy the `bin` folder path (e.g. `C:\ffmpeg\bin`).
  3. Add this directory to your Windows System Environment Variables under `Path`.
  4. Restart the application.

### Issue: "Spotify playlist returned 0 tracks" or "Private Playlist"
* **Cause**: The Spotify playlist is set to "Private", or the playlist link requires user account credentials.
* **Resolution**:
  1. Open Spotify and change the playlist privacy to **Public** or **Unlisted**.
  2. Copy the fresh share link (`https://open.spotify.com/playlist/...`) and paste it into Add Music.

### Issue: "HTTP Error 429: Too Many Requests"
* **Cause**: Upstream streaming platforms rate-limiting rapid consecutive queries.
* **Resolution**:
  1. Wait 60 seconds.
  2. In Settings, lower the **Max Concurrent Download Workers** to 1 or 2.
  3. Click **Retry Failed** in the Downloads view.

---

## 2. Legal Responsibility Disclaimer

Tamil MP3 Downloader is an open-source research and local media management tool. The software contains no bypass mechanisms for Digital Rights Management (DRM) or technical access controls. Users are solely responsible for ensuring that all content acquired complies with applicable copyright laws, licensing terms, and platform agreements.
