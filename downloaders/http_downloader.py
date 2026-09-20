"""
Concurrent HTTP downloader with tqdm progress bars and retry logic.

Features
--------
- Parallel downloads via ThreadPoolExecutor (default 3 workers)
- Per-file progress bars + overall progress via tqdm
- Exponential-backoff retry (3 attempts per file)
- Skips files that already exist (resume-friendly)
- Prefers 320 kbps links; falls back gracefully
- Falls back to sequential mode if concurrent execution fails
"""

import logging
import json
import re
import threading
import time
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
from urllib.parse import unquote, urlparse, parse_qs

import requests
from tqdm import tqdm
try:
    from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TRCK
    from mutagen.mp3 import MP3
    _MUTAGEN_AVAILABLE = True
except Exception:
    APIC = ID3 = TALB = TDRC = TIT2 = TPE1 = TRCK = MP3 = None
    _MUTAGEN_AVAILABLE = False

from downloaders.base import BaseDownloader
from models.song import DownloadResult, Song

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
}

_CHUNK = 131072         # 128 KiB chunks
_COVER_ART_TIMEOUT = 20


class HTTPDownloader(BaseDownloader):
    """Download songs over HTTP with concurrent progress tracking."""

    def __init__(
        self,
        output_dir: Path,
        max_workers: int = 3,
        timeout: int = 90,
        max_retries: int = 3,
        show_progress: bool = True,
    ) -> None:
        super().__init__(output_dir)
        self.max_workers = max_workers
        self.timeout = timeout
        self.max_retries = max_retries
        self.show_progress = bool(show_progress)
        self._tqdm_lock = threading.RLock()
        self._state_lock = threading.RLock()
        tqdm.set_lock(self._tqdm_lock)
        if not _MUTAGEN_AVAILABLE:
            logger.warning("mutagen is unavailable; ID3 tagging will be skipped.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_song(
        self,
        song: Song,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> DownloadResult:
        """Download a single song (blocking, no rich UI)."""
        album_dir = self._album_dir(song.album_name, year=song.year)
        return self._download_with_progress(song, album_dir, pbar=None, progress_cb=progress_cb)

    def download_songs(self, songs: List[Song]) -> List[DownloadResult]:
        """Sequential download – used as fallback."""
        return super().download_songs(songs)

    def download_concurrent(
        self,
        songs: List[Song],
        album_name: str,
        max_workers: Optional[int] = None,
        year: Optional[int] = None,
    ) -> List[DownloadResult]:
        """
        Download all songs concurrently with tqdm progress bars.

        Parameters
        ----------
        songs        : list of Song objects to download
        album_name   : used as the sub-folder name under output_dir
        max_workers  : thread count (default = self.max_workers)
        year         : release year for organised output/year/album/ path
        """
        workers = max(1, int(max_workers if max_workers is not None else self.max_workers))
        album_dir = self._album_dir(album_name, year=year)
        results: List[Optional[DownloadResult]] = [None] * len(songs)
        pending_indices = set(range(len(songs)))
        slot_pool: Queue[int] = Queue()
        for position in range(1, workers + 1):
            slot_pool.put(position)

        if not songs:
            return []

        with tqdm(
            total=len(songs),
            desc="Downloads",
            unit="file",
            dynamic_ncols=True,
            position=0,
            disable=not self.show_progress,
        ) as overall:
            concurrent_failed = False
            try:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = {
                        pool.submit(
                            self._concurrent_worker,
                            idx=i,
                            song=song,
                            album_dir=album_dir,
                            total_songs=len(songs),
                            slot_pool=slot_pool,
                        ): i
                        for i, song in enumerate(songs)
                    }
                    for fut in as_completed(futures):
                        idx = futures[fut]
                        counted = False
                        try:
                            result = fut.result()
                            results[idx] = result
                            pending_indices.discard(idx)
                            counted = True
                        except Exception as exc:
                            concurrent_failed = True
                            logger.error(
                                "Concurrent worker failed for '%s': %s",
                                songs[idx].display_name,
                                exc,
                                exc_info=True,
                            )
                        finally:
                            if counted:
                                overall.update(1)
            except Exception as exc:
                concurrent_failed = True
                logger.error("Concurrent download orchestration failed: %s", exc, exc_info=True)
                # We only know completed entries by checking results.
                pending_indices = {i for i, r in enumerate(results) if r is None}

            if concurrent_failed:
                remaining = [i for i in sorted(pending_indices) if results[i] is None]
                if remaining:
                    msg = "Concurrent mode hit an error. Falling back to sequential downloads..."
                    if self.show_progress:
                        tqdm.write(msg)
                    else:
                        logger.warning(msg)
                    for idx in remaining:
                        song = songs[idx]
                        position = 1
                        label = f"[fallback {idx + 1}/{len(songs)}] {self._short_label(song)}"
                        with tqdm(
                            total=0,
                            desc=label,
                            unit="B",
                            unit_scale=True,
                            unit_divisor=1024,
                            dynamic_ncols=True,
                            position=position,
                            leave=False,
                            disable=not self.show_progress,
                        ) as pbar:
                            results[idx] = self._download_with_progress(song, album_dir, pbar=pbar)
                        overall.update(1)

        return [r for r in results if r is not None]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _album_dir(self, album_name: str, year: Optional[int] = None) -> Path:
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", album_name).strip() or "Unknown"
        if year:
            d = self.output_dir / str(year) / safe
        else:
            d = self.output_dir / safe
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _short_label(song: Song) -> str:
        label = song.display_name[:40]
        if song.is_zip:
            label = f"[ZIP] {label}"
        return label

    @staticmethod
    def _state_path(dest_dir: Path) -> Path:
        """Path to the per-album download state file."""
        return dest_dir / ".download_state.json"

    @staticmethod
    def _norm_name(value: str) -> str:
        return re.sub(r"[^a-z0-9]", "", value.lower())

    def _find_existing_song_file(self, song: Song, dest_dir: Path) -> Optional[Path]:
        """Return an existing file path that likely matches this song by normalized name."""
        target = self._norm_name(song.display_name)
        if not target or not dest_dir.exists():
            return None

        patterns = ["*.mp3"]
        if song.is_zip:
            patterns = ["*.zip"]

        for pattern in patterns:
            for p in dest_dir.glob(pattern):
                try:
                    if p.is_file() and p.stat().st_size > 0 and self._norm_name(p.stem) == target:
                        return p
                except Exception:
                    continue
        return None

    @staticmethod
    def _safe_int(value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _load_state(self, state_path: Path) -> Dict[str, Any]:
        if not state_path.exists():
            return {}
        try:
            with open(state_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_state(self, state_path: Path, state: Dict[str, Any]) -> None:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2, ensure_ascii=False)
        tmp_path.replace(state_path)

    def _update_state_entry(self, state_path: Path, key: str, entry: Dict[str, Any]) -> None:
        with self._state_lock:
            state = self._load_state(state_path)
            state[key] = entry
            self._save_state(state_path, state)

    @staticmethod
    def _is_mp3_file(path: Path) -> bool:
        return path.suffix.lower() == ".mp3"

    def _cover_art_payload(self, song: Song) -> Optional[Tuple[bytes, str]]:
        """Return cover art bytes + mime type when available."""
        if song.cover_art_bytes:
            return song.cover_art_bytes, "image/jpeg"
        if not song.cover_art_url:
            return None

        timeout = min(self.timeout, _COVER_ART_TIMEOUT)
        try:
            with requests.get(song.cover_art_url, headers=_HEADERS, timeout=timeout) as resp:
                if resp.status_code != 200 or not resp.content:
                    return None
                content_type = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
                if not content_type.startswith("image/"):
                    return None
                return resp.content, content_type
        except Exception as exc:
            logger.debug("Cover art fetch failed for '%s': %s", song.display_name, exc)
            return None

    def _apply_id3_tags(self, song: Song, file_path: Path) -> None:
        """
        Apply ID3 tags after download completes.

        Tagging is intentionally non-fatal to avoid breaking downloads.
        """
        if not _MUTAGEN_AVAILABLE or not self._is_mp3_file(file_path):
            return

        try:
            audio = MP3(str(file_path), ID3=ID3)
            if audio.tags is None:
                audio.add_tags()
            tags = audio.tags
            if tags is None:
                return

            tags.delall("TIT2")
            tags.add(TIT2(encoding=3, text=song.display_name))

            artist = (song.artist or "Unknown Artist").strip() or "Unknown Artist"
            tags.delall("TPE1")
            tags.add(TPE1(encoding=3, text=[artist]))

            album_title = (song.album_title or song.album_name or "").strip()
            if album_title:
                tags.delall("TALB")
                tags.add(TALB(encoding=3, text=album_title))

            if song.year:
                tags.delall("TDRC")
                tags.add(TDRC(encoding=3, text=str(song.year)))

            if song.track_number:
                tags.delall("TRCK")
                tags.add(TRCK(encoding=3, text=str(song.track_number)))

            cover_art = self._cover_art_payload(song)
            if cover_art is not None:
                cover_bytes, mime = cover_art
                tags.delall("APIC")
                tags.add(
                    APIC(
                        encoding=3,
                        mime=mime or "image/jpeg",
                        type=3,
                        desc="Cover",
                        data=cover_bytes,
                    )
                )

            audio.save(v2_version=3)
        except Exception as exc:
            logger.warning("ID3 tagging failed for '%s': %s", song.display_name, exc)

    # ------------------------------------------------------------------
    # Core download logic
    # ------------------------------------------------------------------

    def _download_with_progress(
        self,
        song: Song,
        dest_dir: Path,
        pbar: Optional[tqdm] = None,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> DownloadResult:
        """Resolve URL, download with progress, retry on failure."""

        # ---- choose best URL (prefer 320kbps) ----
        url = self._best_url(song.url)

        for attempt in range(self.max_retries):
            try:
                result = self._attempt_download(song, url, dest_dir, pbar, progress_cb)
                if result.success:
                    return result
                # non-retriable HTTP errors
                if "404" in (result.error_message or ""):
                    return result
                # else retry
            except Exception as e:
                if attempt == self.max_retries - 1:
                    return DownloadResult(
                        success=False,
                        song_name=song.display_name,
                        error_message=str(e),
                    )
            if attempt < self.max_retries - 1:
                time.sleep(2 ** attempt)   # 1s, 2s back-off

        return DownloadResult(
            success=False,
            song_name=song.display_name,
            error_message="Max retries exceeded",
        )

    def _attempt_download(
        self,
        song: Song,
        url: str,
        dest_dir: Path,
        pbar: Optional[tqdm] = None,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> DownloadResult:
        """Single download attempt (no retry logic here)."""

        # ---- resolve redirects first ----
        head_headers: Dict[str, Any] = {}
        try:
            head = requests.head(
                url, headers=_HEADERS, allow_redirects=True,
                timeout=min(self.timeout, 10)
            )
            final_url = head.url
            head_headers = dict(head.headers or {})
        except Exception:
            final_url = url

        # ---- determine output path ----
        out_path = self._output_path(song, dest_dir, final_url)
        tmp_path = out_path.with_suffix(out_path.suffix + ".part")
        state_path = self._state_path(dest_dir)
        state_key = out_path.name
        known_total = self._safe_int(head_headers.get("content-length")) or None

        if out_path.exists() and out_path.stat().st_size > 0:
            # Already downloaded
            sz = out_path.stat().st_size
            if pbar is not None:
                pbar.total = sz
                pbar.n = sz
                pbar.set_postfix_str("completed")
                pbar.refresh()
            self._update_state_entry(
                state_path,
                state_key,
                {
                    "url": final_url,
                    "file_name": out_path.name,
                    "downloaded": sz,
                    "total": known_total or sz,
                    "completed": True,
                },
            )
            return DownloadResult(
                success=True,
                song_name=song.display_name,
                file_path=out_path,
                size_downloaded=0,
            )

        # Check for an already-downloaded file with same normalized song name.
        existing_match = self._find_existing_song_file(song, dest_dir)
        if existing_match is not None:
            sz = existing_match.stat().st_size
            self._update_state_entry(
                state_path,
                existing_match.name,
                {
                    "url": final_url,
                    "file_name": existing_match.name,
                    "downloaded": sz,
                    "total": sz,
                    "completed": True,
                },
            )
            return DownloadResult(
                success=True,
                song_name=song.display_name,
                file_path=existing_match,
                size_downloaded=0,
            )

        # ---- streaming GET (resume if partial file exists) ----
        resume_from = tmp_path.stat().st_size if tmp_path.exists() else 0
        headers = dict(_HEADERS)
        requested_resume = resume_from > 0
        if requested_resume:
            headers["Range"] = f"bytes={resume_from}-"

        resp = requests.get(final_url, headers=headers, stream=True, timeout=self.timeout)

        if requested_resume and resp.status_code == 416:
            # Requested range is no longer valid; reset and retry from start.
            resp.close()
            resume_from = 0
            headers = dict(_HEADERS)
            resp = requests.get(final_url, headers=headers, stream=True, timeout=self.timeout)

        if resp.status_code == 404:
            return DownloadResult(
                success=False,
                song_name=song.display_name,
                error_message=f"404 Not Found: {final_url}",
            )
        resp.raise_for_status()

        resumed = requested_resume and resp.status_code == 206 and resume_from > 0
        if requested_resume and not resumed:
            # Server ignored range request; restart this file from scratch.
            resume_from = 0

        remaining = int(resp.headers.get("content-length", 0)) or None
        if resumed and remaining is not None:
            total = resume_from + remaining
        else:
            total = remaining or known_total

        downloaded = resume_from
        if pbar is not None and resumed:
            pbar.set_postfix_str("resumed")

        if pbar is not None:
            pbar.reset(total=total)
            if downloaded:
                pbar.update(downloaded)
            pbar.refresh()

        self._update_state_entry(
            state_path,
            state_key,
            {
                "url": final_url,
                "file_name": out_path.name,
                "downloaded": downloaded,
                "total": total,
                "completed": False,
            },
        )

        start_time = time.time()
        last_progress_time = start_time
        try:
            write_mode = "ab" if resumed else "wb"
            with open(tmp_path, write_mode) as fh:
                for chunk in resp.iter_content(chunk_size=_CHUNK):
                    if chunk:
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if pbar is not None:
                            pbar.update(len(chunk))
                        now = time.time()
                        if progress_cb and (now - last_progress_time >= 0.5 or (total and downloaded >= total)):
                            last_progress_time = now
                            elapsed = max(0.001, now - start_time)
                            speed = (downloaded - resume_from) / elapsed
                            if speed > 1024 * 1024:
                                spd_str = f"{speed / (1024*1024):.1f} MB/s"
                            else:
                                spd_str = f"{speed / 1024:.0f} KB/s"
                            eta_str = ""
                            if total and speed > 0:
                                rem = max(0, total - downloaded)
                                eta_s = int(rem / speed)
                                eta_str = f"{eta_s//60:02d}:{eta_s%60:02d} remaining"
                            ratio = (downloaded / total) if (total and total > 0) else 0.0
                            detail = [spd_str]
                            if eta_str:
                                detail.append(eta_str)
                            progress_cb(ratio, " · ".join(detail))

            tmp_path.rename(out_path)

            # Invariant: Verify that downloaded file is genuine audio and not an HTML error/anti-bot payload
            if not self._is_valid_audio_file(out_path):
                if out_path.exists():
                    out_path.unlink()
                logger.error("Download payload for '%s' failed audio validation (HTML or corrupt)", song.display_name)
                return DownloadResult(
                    success=False,
                    song_name=song.display_name,
                    error_message="Downloaded content is not valid audio (HTML error page or corrupted stream)",
                )

            self._apply_id3_tags(song, out_path)
        except Exception:
            self._update_state_entry(
                state_path,
                state_key,
                {
                    "url": final_url,
                    "file_name": out_path.name,
                    "downloaded": downloaded,
                    "total": total,
                    "completed": False,
                },
            )
            raise
        finally:
            try:
                resp.close()
            except Exception:
                pass

        self._update_state_entry(
            state_path,
            state_key,
            {
                "url": final_url,
                "file_name": out_path.name,
                "downloaded": downloaded,
                "total": total or downloaded,
                "completed": True,
            },
        )

        return DownloadResult(
            success=True,
            song_name=song.display_name,
            file_path=out_path,
            size_downloaded=downloaded,
        )

    def _is_valid_audio_file(self, file_path: Path) -> bool:
        """Verify downloaded file is a valid audio file and not HTML / corrupt data."""
        if not file_path.exists() or file_path.stat().st_size == 0:
            return False
        try:
            with open(file_path, "rb") as f:
                header = f.read(512)
            if len(header) < 4:
                return False
            lower_header = header.lower()
            if b"<!doctype" in lower_header or b"<html" in lower_header or b"<head" in lower_header or b"cloudflare" in lower_header:
                return False
            if header.startswith(b"ID3"):
                return True
            if header[0] == 0xFF and (header[1] & 0xE0) == 0xE0:
                return True
            if b"ftyp" in header[:32]:
                return True
            if header.startswith(b"RIFF") and b"WAVE" in header[:16]:
                return True
            if _MUTAGEN_AVAILABLE and MP3 is not None:
                try:
                    MP3(str(file_path))
                    return True
                except Exception:
                    pass
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------

    @staticmethod
    def _best_url(url: str) -> str:
        """
        If a URL has both 128 and 320 variants, prefer 320.
        Otherwise return unchanged.
        """
        if "128" in url and "320" not in url:
            candidate = url.replace("128", "320")
            try:
                r = requests.head(candidate, headers=_HEADERS, timeout=10, allow_redirects=True)
                if r.status_code == 200:
                    return candidate
            except Exception:
                pass
        return url

    @staticmethod
    def _output_path(song: Song, dest_dir: Path, final_url: str) -> Path:
        """Derive a clean output path from the song and final URL."""
        valid_exts = (".mp3", ".m4a", ".wav", ".flac", ".aac", ".ogg", ".zip", ".webm")
        url_filename = unquote(final_url.split("?")[0].split("/")[-1])
        if url_filename and url_filename.lower().endswith(valid_exts):
            safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", url_filename).strip()
        else:
            # Check if query parameter has a path/file with audio extension (e.g. download.php?path=.../Song.mp3)
            parsed = urlparse(final_url)
            query_dict = parse_qs(parsed.query)
            extracted_name = None
            for key in ["path", "file", "name", "filename"]:
                vals = query_dict.get(key, [])
                if vals:
                    candidate = unquote(vals[0].split("/")[-1])
                    if candidate.lower().endswith(valid_exts):
                        extracted_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", candidate).strip()
                        break
            safe = extracted_name or song.safe_filename
        return dest_dir / (safe or "download.mp3")

    def _concurrent_worker(
        self,
        idx: int,
        song: Song,
        album_dir: Path,
        total_songs: int,
        slot_pool: Queue[int],
    ) -> DownloadResult:
        """
        Execute one concurrent download with a dedicated tqdm progress bar slot.

        Using per-worker slots keeps tqdm output stable while downloads run in parallel.
        """
        position = slot_pool.get()
        try:
            label = f"[{idx + 1}/{total_songs}] {self._short_label(song)}"
            with tqdm(
                total=0,
                desc=label,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                dynamic_ncols=True,
                position=position,
                leave=False,
                disable=not self.show_progress,
            ) as pbar:
                return self._download_with_progress(song, album_dir, pbar=pbar)
        finally:
            slot_pool.put(position)
