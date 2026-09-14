"""
Regional Tamil music audio provider bridging MassTamilan, TamilMP3, and FriendsTamilMP3.
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Callable

from library.providers.base import (
    AudioProvider, AudioCandidate, ResolvedStream, ProviderCapabilities, DownloadResult
)
from scrapers.source_registry import SourceRegistry
from downloaders.http_downloader import HTTPDownloader
from models.song import Song as DownloadSong

logger = logging.getLogger(__name__)


class TamilRegionalProvider(AudioProvider):
    """
    Audio provider leveraging existing verified Tamil music web scrapers.
    """

    def __init__(self, source_registry: Optional[SourceRegistry] = None):
        self.source_registry = source_registry or SourceRegistry()

    @property
    def name(self) -> str:
        return "tamil_regional"

    @property
    def display_name(self) -> str:
        return "Tamil Music Sources (MassTamilan / TamilMP3)"

    def is_available(self) -> bool:
        # Usable if at least one core regional source is healthy
        sources = self.source_registry.get_all_sources()
        return any(s.enabled and s.is_usable for s in sources)

    def get_capabilities(self) -> ProviderCapabilities:
        sources = [s for s in self.source_registry.get_all_sources() if s.enabled and s.is_usable]
        names = ", ".join(s.display_name for s in sources)
        return ProviderCapabilities(
            name=self.name,
            display_name=self.display_name,
            supports_search=True,
            supports_direct_url=True,
            max_quality_kbps=320,
            is_operational=len(sources) > 0,
            notes=f"Active sources: {names}" if sources else "No regional sources available",
        )

    def search(
        self,
        title: str,
        artist: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        limit: int = 5,
    ) -> List[AudioCandidate]:
        """Search across enabled regional scrapers."""
        candidates = []
        sources = [s for s in self.source_registry.get_all_sources() if s.enabled and s.is_usable and s.scraper]

        clean_query = title.strip().lower()

        for reg_src in sources:
            scraper = reg_src.scraper
            try:
                # Search albums by title
                albums = scraper.search(clean_query)
                for album in albums[:2]:
                    songs = scraper.get_songs(album)
                    for s in songs:
                        if clean_query in s.name.lower() or s.name.lower() in clean_query:
                            c = AudioCandidate(
                                provider_name=self.name,
                                source_url=s.url,
                                title=s.name,
                                uploader=album.name,
                                duration_seconds=None,
                                quality_kbps=320 if "320" in s.quality else 128,
                                audio_format="mp3",
                                thumbnail_url=album.image_url,
                                reliability_score=reg_src.reliability_score,
                                raw_metadata={"source_name": reg_src.name, "song_obj": s, "album": album},
                            )
                            candidates.append(c)
                            if len(candidates) >= limit:
                                return candidates
            except Exception as e:
                logger.debug(f"Regional search error on {reg_src.name}: {e}")

        return candidates

    def resolve(self, candidate: AudioCandidate) -> Optional[ResolvedStream]:
        raw = candidate.raw_metadata
        source_name = raw.get("source_name")
        song_obj = raw.get("song_obj")
        reg_src = self.source_registry.get_source(source_name) if source_name else None

        download_url = candidate.source_url
        if reg_src and reg_src.scraper and hasattr(reg_src.scraper, "get_download_url") and song_obj:
            try:
                download_url = reg_src.scraper.get_download_url(song_obj, quality=str(candidate.quality_kbps or 320))
            except Exception as e:
                logger.warning(f"Error resolving download URL for regional candidate: {e}")

        return ResolvedStream(
            stream_url=download_url or candidate.source_url,
            audio_format="mp3",
            quality_kbps=candidate.quality_kbps,
        )

    def download(
        self,
        candidate: AudioCandidate,
        output_dir: Path,
        filename_stem: str,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> DownloadResult:
        """Download using HTTPDownloader."""
        resolved = self.resolve(candidate)
        if not resolved or not resolved.stream_url:
            return DownloadResult(
                success=False,
                error_message="Failed to resolve download URL for regional candidate",
                provider_name=self.name,
            )

        dl_song = DownloadSong(
            name=filename_stem,
            url=resolved.stream_url,
            quality=f"{candidate.quality_kbps or 320}kbps",
            album_name=candidate.uploader or "Tamil Album",
        )

        try:
            downloader = HTTPDownloader(
                output_dir=output_dir,
                max_workers=1,
                show_progress=False,
            )
            res = downloader.download_song(dl_song)
            if res.success and res.file_path and res.file_path.exists() and res.file_path.stat().st_size > 1024:
                return DownloadResult(
                    success=True,
                    file_path=res.file_path,
                    size_bytes=res.file_path.stat().st_size,
                    provider_name=self.name,
                )
            else:
                return DownloadResult(
                    success=False,
                    error_message=res.error_message or "Download verification failed",
                    provider_name=self.name,
                )
        except Exception as e:
            return DownloadResult(
                success=False,
                error_message=str(e),
                provider_name=self.name,
            )
