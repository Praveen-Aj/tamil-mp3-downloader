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
        self._ffmpeg_path = self._find_ffmpeg()
        self._ffmpeg_available = self._ffmpeg_path is not None

    def _find_ffmpeg(self) -> Optional[str]:
        """Locate ffmpeg binary via PATH, imageio-ffmpeg package, or local project bin."""
        p = shutil.which("ffmpeg")
        if p:
            return p
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and os.path.exists(exe):
                return exe
        except Exception:
            pass
        project_bin = Path(__file__).resolve().parent.parent.parent / "bin" / "ffmpeg.exe"
        if project_bin.exists():
            return str(project_bin)
        return None

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
        if self._yt_dlp_available and self._ffmpeg_available:
            notes += " (FFmpeg detected; 320 kbps MP3 conversion active)"
        elif self._yt_dlp_available and not self._ffmpeg_available:
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

        import uuid
        import shutil
        import yt_dlp

        output_dir.mkdir(parents=True, exist_ok=True)
        # Dedicated isolated temporary directory for intermediate download and conversion
        temp_work_dir = output_dir / ".tmp" / f"ytdl_{uuid.uuid4().hex[:8]}"
        temp_work_dir.mkdir(parents=True, exist_ok=True)
        target_template = str(temp_work_dir / f"{filename_stem}.%(ext)s")

        def _hook(d):
            if not progress_cb:
                return
            status = d.get("status")
            if status == "downloading":
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes") or 0
                ratio = (downloaded / total) if total > 0 else 0.0
                speed = d.get("speed")
                speed_str = d.get("_speed_str")
                if not speed_str and speed:
                    if speed > 1024 * 1024:
                        speed_str = f"{speed / (1024*1024):.1f} MB/s"
                    else:
                        speed_str = f"{speed / 1024:.0f} KB/s"
                eta = d.get("eta")
                eta_str = d.get("_eta_str")
                if not eta_str and eta is not None:
                    eta_str = f"{int(eta)//60:02d}:{int(eta)%60:02d}"

                detail = []
                if speed_str:
                    detail.append(speed_str.strip())
                if eta_str:
                    detail.append(f"{eta_str.strip()} remaining")
                msg = " · ".join(detail) if detail else "Downloading..."
                progress_cb(ratio, msg)
            elif status == "finished":
                progress_cb(1.0, "Finalizing audio...")

        ydl_opts: Dict[str, Any] = {
            "outtmpl": target_template,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "progress_hooks": [_hook],
            "format": "bestaudio/best",
        }

        if self._ffmpeg_available and self._ffmpeg_path:
            ydl_opts["ffmpeg_location"] = self._ffmpeg_path
            ydl_opts["postprocessors"] = [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "320",
            }]

        final_result = None
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                error_code = ydl.download([candidate.source_url])
                if error_code != 0:
                    final_result = DownloadResult(
                        success=False,
                        error_message=f"yt-dlp download failed with exit code {error_code}",
                        provider_name=self.name,
                    )
                    return final_result

            # Locate converted/downloaded file in temp_work_dir
            found_temp_file = None
            for ext in [".mp3", ".m4a", ".webm", ".opus", ".aac"]:
                cand_path = temp_work_dir / f"{filename_stem}{ext}"
                if cand_path.exists() and cand_path.stat().st_size > 1024:
                    found_temp_file = cand_path
                    break

            if not found_temp_file:
                matches = list(temp_work_dir.glob(f"{filename_stem}.*"))
                if matches and matches[0].stat().st_size > 1024:
                    found_temp_file = matches[0]

            if found_temp_file and found_temp_file.exists() and found_temp_file.stat().st_size > 0:
                final_dest = output_dir / f"{filename_stem}{found_temp_file.suffix}"
                # Atomically move verified final file to destination
                shutil.move(str(found_temp_file), str(final_dest))
                final_result = DownloadResult(
                    success=True,
                    file_path=final_dest,
                    size_bytes=final_dest.stat().st_size,
                    provider_name=self.name,
                )
                return final_result

            final_result = DownloadResult(
                success=False,
                error_message="Downloaded file missing or empty after completion",
                provider_name=self.name,
            )
            return final_result
        except Exception as e:
            logger.error(f"YouTubeProvider download exception: {e}", exc_info=True)
            final_result = DownloadResult(
                success=False,
                error_message=str(e),
                provider_name=self.name,
            )
            return final_result
        finally:
            # Clean up isolated temporary work directory and all intermediate files
            try:
                if temp_work_dir.exists():
                    shutil.rmtree(str(temp_work_dir), ignore_errors=True)
            except Exception:
                pass

            # Cleanup .tmp directory if empty
            try:
                tmp_parent = output_dir / ".tmp"
                if tmp_parent.exists() and not any(tmp_parent.iterdir()):
                    tmp_parent.rmdir()
            except Exception:
                pass

            # Regression cleanup: ensure no 0-byte or .webm/.part files in output_dir
            for cleanup_file in output_dir.glob(f"{filename_stem}.*"):
                try:
                    if cleanup_file.exists():
                        if cleanup_file.stat().st_size == 0 or cleanup_file.suffix.lower() in [".webm", ".part", ".crdownload"]:
                            cleanup_file.unlink()
                            logger.info(f"Cleaned up incomplete artifact: {cleanup_file}")
                except Exception:
                    pass
