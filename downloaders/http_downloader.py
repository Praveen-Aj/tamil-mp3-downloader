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
import re
import threading
import time
from queue import Queue
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional
from urllib.parse import unquote

import requests
from tqdm import tqdm

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

_CHUNK = 65536          # 64 KiB chunks


class HTTPDownloader(BaseDownloader):
    """Download songs over HTTP with concurrent progress tracking."""

    def __init__(
        self,
        output_dir: Path,
        max_workers: int = 3,
        timeout: int = 90,
        max_retries: int = 3,
    ) -> None:
        super().__init__(output_dir)
        self.max_workers = max_workers
        self.timeout = timeout
        self.max_retries = max_retries
        self._tqdm_lock = threading.RLock()
        tqdm.set_lock(self._tqdm_lock)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_song(self, song: Song) -> DownloadResult:
        """Download a single song (blocking, no rich UI)."""
        album_dir = self._album_dir(song.album_name)
        return self._download_one(song, album_dir)

    def download_songs(self, songs: List[Song]) -> List[DownloadResult]:
        """Sequential download – used as fallback."""
        results = []
        for song in songs:
            results.append(self.download_song(song))
        return results

    def download_concurrent(
        self,
        songs: List[Song],
        album_name: str,
        max_workers: Optional[int] = None,
    ) -> List[DownloadResult]:
        """
        Download all songs concurrently with tqdm progress bars.

        Parameters
        ----------
        songs        : list of Song objects to download
        album_name   : used as the sub-folder name under output_dir
        max_workers  : thread count (default = self.max_workers)
        """
        workers = max(1, int(max_workers if max_workers is not None else self.max_workers))
        album_dir = self._album_dir(album_name)
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
                    tqdm.write(
                        "Concurrent mode hit an error. Falling back to sequential downloads..."
                    )
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
                        ) as pbar:
                            results[idx] = self._download_with_progress(song, album_dir, pbar=pbar)
                        overall.update(1)

        return [r for r in results if r is not None]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _album_dir(self, album_name: str) -> Path:
        safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", album_name).strip() or "Unknown"
        d = self.output_dir / "IsaiminiHQ" / safe
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _short_label(song: Song) -> str:
        label = song.display_name[:40]
        if song.is_zip:
            label = f"[ZIP] {label}"
        return label

    # ------------------------------------------------------------------
    # Core download logic
    # ------------------------------------------------------------------

    def _download_with_progress(
        self,
        song: Song,
        dest_dir: Path,
        pbar: Optional[tqdm] = None,
    ) -> DownloadResult:
        """Resolve URL, download with progress, retry on failure."""

        # ---- choose best URL (prefer 320kbps) ----
        url = self._best_url(song.url)

        for attempt in range(self.max_retries):
            try:
                result = self._attempt_download(song, url, dest_dir, pbar)
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
    ) -> DownloadResult:
        """Single download attempt (no retry logic here)."""

        # ---- resolve redirects first ----
        try:
            head = requests.head(
                url, headers=_HEADERS, allow_redirects=True,
                timeout=self.timeout
            )
            final_url = head.url
        except Exception:
            final_url = url

        # ---- determine output path ----
        out_path = self._output_path(song, dest_dir, final_url)

        if out_path.exists() and out_path.stat().st_size > 0:
            # Already downloaded
            sz = out_path.stat().st_size
            if pbar is not None:
                pbar.total = sz
                pbar.n = sz
                pbar.refresh()
            return DownloadResult(
                success=True,
                song_name=song.display_name,
                file_path=out_path,
                size_downloaded=sz,
            )

        # ---- streaming GET ----
        resp = requests.get(
            final_url, headers=_HEADERS, stream=True, timeout=self.timeout
        )

        if resp.status_code == 404:
            return DownloadResult(
                success=False,
                song_name=song.display_name,
                error_message=f"404 Not Found: {final_url}",
            )
        resp.raise_for_status()

        total = int(resp.headers.get("content-length", 0)) or None
        if pbar is not None:
            pbar.reset(total=total)

        downloaded = 0
        tmp_path = out_path.with_suffix(out_path.suffix + ".part")

        try:
            with open(tmp_path, "wb") as fh:
                for chunk in resp.iter_content(chunk_size=_CHUNK):
                    if chunk:
                        fh.write(chunk)
                        downloaded += len(chunk)
                        if pbar is not None:
                            pbar.update(len(chunk))

            tmp_path.rename(out_path)
        except Exception:
            tmp_path.unlink(missing_ok=True)
            raise

        return DownloadResult(
            success=True,
            song_name=song.display_name,
            file_path=out_path,
            size_downloaded=downloaded,
        )

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
        # Try to get filename from URL first
        url_filename = unquote(final_url.split("?")[0].split("/")[-1])
        if url_filename and ("." in url_filename):
            safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", url_filename).strip()
        else:
            safe = song.safe_filename
        return dest_dir / (safe or "download.mp3")

    def _download_one(self, song: Song, dest_dir: Path) -> DownloadResult:
        """Compatibility helper for single-song downloads without explicit tqdm bar."""
        return self._download_with_progress(song, dest_dir, pbar=None)

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
            ) as pbar:
                return self._download_with_progress(song, album_dir, pbar=pbar)
        finally:
            slot_pool.put(position)
