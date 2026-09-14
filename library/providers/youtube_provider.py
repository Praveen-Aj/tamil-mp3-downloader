"""
YouTube & YouTube Music audio provider implementation powered by yt-dlp.
"""

import logging
import os
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from library.providers.base import (
    AudioProvider, AudioCandidate, ResolvedStream, ProviderCapabilities, DownloadResult
)

logger = logging.getLogger(__name__)


class YouTubeProvider(AudioProvider):
    """
    Audio provider using yt-dlp for YouTube and YouTube Music stream acquisition.
    """

    def __init__(self):
        self._yt_dlp_available = self._check_yt_dlp()
        self._ffmpeg_available = shutil.which("ffmpeg") is not None

    def _check_yt_dlp(self) -> bool:
        try:
            import yt_dlp  # noqa: F401
            return True
        except ImportError:
            return False

    @property
    def name(self) -> str:
        return "youtube"

    @property
    def display_name(self) -> str:
        return "YouTube / YouTube Music"

    def is_available(self) -> bool:
        return self._yt_dlp_available

    def get_capabilities(self) -> ProviderCapabilities:
        notes = "Ready" if self._yt_dlp_available else "yt-dlp package missing"
        if self._yt_dlp_available and not self._ffmpeg_available:
            notes += " (FFmpeg not detected; native container audio will be downloaded)"
        return ProviderCapabilities(
            name=self.name,
            display_name=self.display_name,
            supports_search=True,
            supports_direct_url=True,
            max_quality_kbps=320,
            is_operational=self._yt_dlp_available,
            notes=notes,
        )

    def search(
        self,
        title: str,
        artist: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        limit: int = 5,
    ) -> List[AudioCandidate]:
        """Search YouTube for matching audio candidates."""
        if not self._yt_dlp_available:
            logger.warning("YouTubeProvider search invoked but yt-dlp is not installed")
            return []

        import yt_dlp

        # Construct optimized search query
        query_terms = [title]
        if artist:
            query_terms.append(artist)
        query = " ".join(query_terms)

        ydl_opts = {
            "extract_flat": True,
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
        }

        candidates = []
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                search_res = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
                if not search_res or "entries" not in search_res:
                    return []

                for entry in search_res["entries"]:
                    if not entry:
                        continue
                    v_id = entry.get("id")
                    v_url = entry.get("url") or f"https://www.youtube.com/watch?v={v_id}"
                    c = AudioCandidate(
                        provider_name=self.name,
                        source_url=v_url,
                        title=entry.get("title", ""),
                        uploader=entry.get("uploader") or entry.get("channel"),
                        duration_seconds=int(entry.get("duration") or 0) or None,
                        quality_kbps=256,  # Typical YouTube high audio
                        audio_format="mp3" if self._ffmpeg_available else "m4a",
                        thumbnail_url=entry.get("thumbnail"),
                        reliability_score=0.95,
                        raw_metadata=entry,
                    )
                    candidates.append(c)
        except Exception as e:
            logger.warning(f"YouTubeProvider search error for query '{query}': {e}")

        return candidates

    def resolve(self, candidate: AudioCandidate) -> Optional[ResolvedStream]:
        """Resolve candidate to stream URL if direct stream extraction is requested."""
        if not self._yt_dlp_available:
            return None

        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(candidate.source_url, download=False)
                if not info:
                    return None
                stream_url = info.get("url")
                if stream_url:
                    return ResolvedStream(
                        stream_url=stream_url,
                        audio_format=info.get("ext", "mp3"),
                        quality_kbps=info.get("abr", 256),
                        headers=info.get("http_headers", {}),
                    )
        except Exception as e:
            logger.warning(f"Failed to resolve stream for {candidate.source_url}: {e}")

        return None

    def download(
        self,
        candidate: AudioCandidate,
        output_dir: Path,
        filename_stem: str,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> DownloadResult:
        """Download candidate using yt-dlp with sanitized naming and fallback."""
        if not self._yt_dlp_available:
            return DownloadResult(
                success=False,
                error_message="yt-dlp is not installed in the environment.",
                provider_name=self.name,
            )

        import yt_dlp

        output_dir.mkdir(parents=True, exist_ok=True)
        # Target path pattern
        target_template = str(output_dir / f"{filename_stem}.%(ext)s")

        def _hook(d):
            if progress_cb and d.get("status") == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                ratio = (downloaded / total) if total > 0 else 0.0
                speed_str = d.get("_speed_str", "")
                progress_cb(ratio, f"Downloading: {speed_str}")

        ydl_opts: Dict[str, Any] = {
            "outtmpl": target_template,
            "quiet": True,
            "no_warnings": True,
            "progress_hooks": [_hook],
            "format": "bestaudio/best",
        }

        if self._ffmpeg_available:
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                error_code = ydl.download([candidate.source_url])
                if error_code != 0:
                    return DownloadResult(
                        success=False,
                        error_message=f"yt-dlp download failed with exit code {error_code}",
                        provider_name=self.name,
                    )

            # Locate downloaded file
            # Could be .mp3, .m4a, .webm, .opus
            for ext in [".mp3", ".m4a", ".webm", ".opus", ".aac"]:
                cand_path = output_dir / f"{filename_stem}{ext}"
                if cand_path.exists() and cand_path.stat().st_size > 1024:
                    return DownloadResult(
                        success=True,
                        file_path=cand_path,
                        size_bytes=cand_path.stat().st_size,
                        provider_name=self.name,
                    )

            # Search any created file starting with filename_stem
            matches = list(output_dir.glob(f"{filename_stem}.*"))
            if matches and matches[0].stat().st_size > 1024:
                return DownloadResult(
                    success=True,
                    file_path=matches[0],
                    size_bytes=matches[0].stat().st_size,
                    provider_name=self.name,
                )

            return DownloadResult(
                success=False,
                error_message="Downloaded file missing or empty after completion",
                provider_name=self.name,
            )
        except Exception as e:
            logger.error(f"YouTubeProvider download exception: {e}", exc_info=True)
            return DownloadResult(
                success=False,
                error_message=str(e),
                provider_name=self.name,
            )
