# Audio Provider Architecture & Selection Strategy

## 1. Overview

The Audio Provider abstraction decouples user-facing platform URLs from actual audio streams.

When a user submits a music URL (such as a Spotify track or playlist), Spotify acts solely as a **Canonical Metadata Provider**. The application never attempts to stream from Spotify directly. Instead, the requested track is matched against registered **Audio Providers** to identify, rank, and download the best available audio stream.

---

## 2. Pluggable Architecture

All audio providers implement the abstract class [`AudioProvider`](file:///c:/Users/Praveen/Downloads/Python%20Scripts/tamil-mp3-downloader/library/providers/base.py):

```python
class AudioProvider(ABC):
    @property
    def name(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    def is_available(self) -> bool: ...
    def get_capabilities(self) -> ProviderCapabilities: ...
    def search(self, title: str, artist: str, duration: int) -> List[AudioCandidate]: ...
    def resolve(self, candidate: AudioCandidate) -> Optional[ResolvedStream]: ...
    def download(self, candidate: AudioCandidate, output_dir: Path, filename_stem: str) -> DownloadResult: ...
    def validate(self, file_path: Path) -> bool: ...
```

---

## 3. Registered Core Providers

1. **`YouTubeProvider` (Priority 1)**:
   * Engine: `yt-dlp`
   * Capabilities: High-speed metadata extraction (`extract_flat=True`), global YouTube and YouTube Music catalog search.
   * Format: Extracts best audio stream (`mp3` when FFmpeg is present, or native container `.m4a` when FFmpeg is absent).
2. **`TamilRegionalProvider` (Priority 2)**:
   * Engine: Direct scraping bridge to verified regional sources (`MassTamilan`, `TamilMP3`, `FriendsTamilMP3`).
   * Capabilities: High-bitrate 320 kbps dedicated film album tracks.
3. **`DirectAudioProvider` (Priority 3)**:
   * Engine: Direct HTTP chunked streaming for explicit `.mp3`, `.m4a`, and `.wav` URLs.

---

## 4. Multi-Factor Match Evaluation & Scoring

Candidates returned by providers are evaluated by [`TrackMatcher`](file:///c:/Users/Praveen/Downloads/Python%20Scripts/tamil-mp3-downloader/library/matching/matcher.py) using a composite similarity formula:

$$\text{Score} = 0.45 \cdot S_{\text{title}} + 0.30 \cdot S_{\text{artist}} + 0.25 \cdot S_{\text{duration}}$$

* **Title Similarity ($S_{\text{title}}$)**: Strips noisy descriptors (`(Official Video)`, `[Lyrics]`, `4K`, `320kbps`, `MassTamilan`) and computes a weighted blend of Levenshtein sequence matching and token set overlap.
* **Duration Similarity ($S_{\text{duration}}$)**:
  * $|\Delta t| \le 5\text{s} \implies 1.0$
  * $|\Delta t| \le 15\text{s} \implies 0.85$
  * $|\Delta t| \le 30\text{s} \implies 0.60$
  * $|\Delta t| > 90\text{s} \implies$ heavily penalized ($40\%$ of score).

### Confidence Classification:
* **`HIGH CONFIDENCE` ($\ge 82\%$)**: Auto-selected and marked `READY` for immediate batch download.
* **`MEDIUM CONFIDENCE` ($60\% - 81\%$)**: Flagged as `NEEDS REVIEW` in the UI to allow user verification.
* **`LOW CONFIDENCE` ($< 60\%$)**: Marked `NEEDS REVIEW` / skipped by default to prevent incorrect audio matching.
* **`NO MATCH`**: Marked `NO SOURCE`.

---

## 5. Automatic Fallback Execution

When a playlist batch is executed:
1. Provider 1 candidate is attempted first.
2. If network failure, rate limiting, or file validation fails, the engine automatically attempts Provider 2.
3. Partial playlist failures never abort the entire batch; remaining tracks proceed normally, and failed tracks are isolated for one-click retry.
