"""
Direct HTTP audio stream provider for .mp3, .m4a, and audio web links.
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable
import requests

from library.providers.base import (
    AudioProvider, AudioCandidate, ResolvedStream, ProviderCapabilities, DownloadResult
)

logger = logging.getLogger(__name__)


class DirectAudioProvider(AudioProvider):
    """
    Handles direct HTTP/HTTPS URLs pointing directly to audio files.
    """

    @property
    def name(self) -> str:
        return "direct_http"

    @property
    def display_name(self) -> str:
        return "Direct Audio Link (HTTP/HTTPS)"

    def is_available(self) -> bool:
        return True

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name=self.name,
            display_name=self.display_name,
            supports_search=False,
            supports_direct_url=True,
            max_quality_kbps=320,
            is_operational=True,
            notes="Direct .mp3/.m4a/.wav links",
        )

    def search(
        self,
        title: str,
        artist: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        limit: int = 5,
    ) -> List[AudioCandidate]:
        # Direct provider does not support arbitrary text search
        return []

    def resolve(self, candidate: AudioCandidate) -> Optional[ResolvedStream]:
        ext = "mp3"
        if "." in candidate.source_url:
            potential_ext = candidate.source_url.split("?")[0].split(".")[-1].lower()
            if potential_ext in ["mp3", "m4a", "flac", "wav", "aac"]:
                ext = potential_ext

        return ResolvedStream(
            stream_url=candidate.source_url,
            audio_format=ext,
            quality_kbps=candidate.quality_kbps or 320,
        )

    def download(
        self,
        candidate: AudioCandidate,
        output_dir: Path,
        filename_stem: str,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> DownloadResult:
        """Download stream directly via HTTP chunking."""
        output_dir.mkdir(parents=True, exist_ok=True)
        resolved = self.resolve(candidate)
        if not resolved:
            return DownloadResult(
                success=False,
                error_message="Failed to resolve direct audio URL",
                provider_name=self.name,
            )

        target_file = output_dir / f"{filename_stem}.{resolved.audio_format}"
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
            resp = requests.get(resolved.stream_url, stream=True, timeout=(15, 60), headers=headers)
            resp.raise_for_status()

            total_size = int(resp.headers.get("content-length", 0))
            downloaded = 0

            with open(target_file, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb and total_size > 0:
                            progress_cb(downloaded / total_size, f"Downloading: {downloaded // 1024} KB")

            if target_file.exists() and target_file.stat().st_size > 1024:
                if total_size > 0 and downloaded < total_size:
                    raise IOError(f"Incomplete download: received {downloaded} of {total_size} bytes")
                if progress_cb:
                    progress_cb(1.0, f"Downloaded: {target_file.name}")
                return DownloadResult(
                    success=True,
                    file_path=target_file,
                    size_bytes=target_file.stat().st_size,
                    provider_name=self.name,
                )
            else:
                return DownloadResult(
                    success=False,
                    error_message="Downloaded file empty or too small",
                    provider_name=self.name,
                )
        except Exception as e:
            if target_file.exists():
                try:
                    target_file.unlink()
                except Exception:
                    pass
            return DownloadResult(
                success=False,
                error_message=str(e),
                provider_name=self.name,
            )
