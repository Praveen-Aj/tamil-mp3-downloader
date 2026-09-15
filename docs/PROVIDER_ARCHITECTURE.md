# Audio Provider Architecture & Selection Strategy

## 1. Overview

The Audio Provider abstraction completely decouples user-facing platform metadata from physical audio streams.

When a user submits a music URL (such as a Spotify track or playlist) or searches by title, the platform source acts solely as a **Metadata Provider**. The application does not require user intervention to pick streams; instead, the requested track is automatically matched against registered **Audio Providers** to identify, rank, and download the best available verified audio stream.

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

## 4. Multi-Factor Match Evaluation & Autonomous Scoring

Candidates returned by providers are evaluated by [`TrackMatcher`](file:///c:/Users/Praveen/Downloads/Python%20Scripts/tamil-mp3-downloader/library/matching/matcher.py) using a composite similarity formula:

$$\text{Score} = 0.45 \cdot S_{\text{title}} + 0.30 \cdot S_{\text{artist}} + 0.25 \cdot S_{\text{duration}}$$

* **Title Similarity ($S_{\text{title}}$)**: Strips noisy descriptors (`(Official Video)`, `[Lyrics]`, `4K`, `320kbps`, `MassTamilan`) and computes a weighted blend of Levenshtein sequence matching and token set overlap.
* **Duration Similarity ($S_{\text{duration}}$)**:
  * $|\Delta t| \le 5\text{s} \implies 1.0$
  * $|\Delta t| \le 15\text{s} \implies 0.85$
  * $|\Delta t| \le 30\text{s} \implies 0.60$
  * $|\Delta t| > 90\text{s} \implies$ heavily penalized ($40\%$ of score).

### Autonomous Ranking & Selection:
The provider pipeline sorts all candidate streams by match score and audio bitrate. The best match is selected automatically. The end-user is never burdened with reviewing candidate lists or configuring match percentages.

---

## 5. Autonomous Fallback & Stream Validation Execution

When a track download executes:
1. The highest-ranked candidate audio stream is attempted first.
2. The downloaded file is verified via binary header inspection (`_is_valid_audio_file`) to reject corrupted streams or HTML block pages.
3. If network errors, HTTP rate limits (429/503), or validation failures occur, the engine automatically falls back to the next best provider candidate in the hierarchy.
4. Partial playlist failures never abort the entire batch; remaining tracks proceed smoothly, and failed items are kept in the queue for automatic or one-click retry.
