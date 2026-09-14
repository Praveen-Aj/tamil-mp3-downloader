"""
Central registry and fallback manager for Audio Providers.
"""

import logging
from pathlib import Path
from typing import Optional, List, Dict, Tuple, Callable

from library.providers.base import AudioProvider, AudioCandidate, DownloadResult, ProviderCapabilities
from library.providers.youtube_provider import YouTubeProvider
from library.providers.regional_provider import TamilRegionalProvider
from library.providers.direct_provider import DirectAudioProvider
from library.matching.matcher import TrackMatcher, MatchResult, ConfidenceTier

logger = logging.getLogger(__name__)


class ProviderRegistry:
    """
    Manages audio providers, priority ranking, candidate evaluation, and fallback execution.
    """

    def __init__(self, matcher: Optional[TrackMatcher] = None):
        self.matcher = matcher or TrackMatcher()
        self._providers: Dict[str, AudioProvider] = {}
        self._priority: List[str] = []
        self._init_default_providers()

    def _init_default_providers(self) -> None:
        """Register default core audio providers."""
        yt = YouTubeProvider()
        self.register_provider(yt)

        reg = TamilRegionalProvider()
        self.register_provider(reg)

        direct = DirectAudioProvider()
        self.register_provider(direct)

    def register_provider(self, provider: AudioProvider) -> None:
        """Register a provider and add it to priority list if not present."""
        self._providers[provider.name] = provider
        if provider.name not in self._priority:
            self._priority.append(provider.name)

    def get_provider(self, name: str) -> Optional[AudioProvider]:
        return self._providers.get(name)

    def get_all_providers(self) -> List[AudioProvider]:
        return [self._providers[name] for name in self._priority if name in self._providers]

    def get_operational_providers(self) -> List[AudioProvider]:
        return [p for p in self.get_all_providers() if p.is_available()]

    def search_and_rank_candidates(
        self,
        title: str,
        artist: Optional[str] = None,
        duration_seconds: Optional[int] = None,
        preferred_provider: Optional[str] = None,
        limit_per_provider: int = 3,
    ) -> List[Tuple[AudioCandidate, MatchResult]]:
        """
        Query providers in priority order and rank all candidates with TrackMatcher.
        Returns list of (candidate, MatchResult) sorted by match score descending.
        """
        all_candidates: List[AudioCandidate] = []

        providers_to_query = []
        if preferred_provider and preferred_provider in self._providers:
            providers_to_query.append(self._providers[preferred_provider])

        for name in self._priority:
            p = self._providers.get(name)
            if p and p not in providers_to_query and p.is_available():
                providers_to_query.append(p)

        for p in providers_to_query:
            try:
                cands = p.search(title=title, artist=artist, duration_seconds=duration_seconds, limit=limit_per_provider)
                all_candidates.extend(cands)
            except Exception as e:
                logger.warning(f"Error querying provider {p.name}: {e}")

        # Evaluate each candidate with TrackMatcher
        scored_pairs: List[Tuple[AudioCandidate, MatchResult]] = []
        for cand in all_candidates:
            res = self.matcher.evaluate(
                target_title=title,
                target_artist=artist,
                target_duration=duration_seconds,
                candidate_title=cand.title,
                candidate_uploader=cand.uploader,
                candidate_duration=cand.duration_seconds,
                candidate_quality_kbps=cand.quality_kbps,
            )
            scored_pairs.append((cand, res))

        # Sort by score descending (high confidence first)
        scored_pairs.sort(key=lambda item: item[1].score, reverse=True)
        return scored_pairs

    def download_with_fallback(
        self,
        candidates: List[AudioCandidate],
        output_dir: Path,
        filename_stem: str,
        progress_cb: Optional[Callable[[float, str], None]] = None,
    ) -> DownloadResult:
        """
        Attempt downloading candidates in order. If one fails, automatically falls back to the next.
        """
        if not candidates:
            return DownloadResult(
                success=False,
                error_message="No audio candidates provided for download.",
            )

        last_error = "Unknown error"
        for idx, candidate in enumerate(candidates, start=1):
            provider = self.get_provider(candidate.provider_name)
            if not provider or not provider.is_available():
                continue

            if progress_cb:
                progress_cb(0.05, f"Trying source {idx}/{len(candidates)} ({provider.display_name})...")

            result = provider.download(
                candidate=candidate,
                output_dir=output_dir,
                filename_stem=filename_stem,
                progress_cb=progress_cb,
            )

            if result.success and result.file_path and provider.validate(result.file_path):
                return result
            else:
                last_error = result.error_message or "Validation failed"
                logger.warning(
                    f"Candidate download failed from {candidate.provider_name}: {last_error}. Trying fallback..."
                )

        return DownloadResult(
            success=False,
            error_message=f"All candidate sources failed. Last reason: {last_error}",
        )
