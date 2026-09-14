"""
Multi-factor candidate match evaluation and confidence scoring engine.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from typing import Optional


class ConfidenceTier(Enum):
    """Match confidence classification."""
    HIGH = "HIGH CONFIDENCE"
    MEDIUM = "MEDIUM CONFIDENCE"
    LOW = "LOW CONFIDENCE"
    NO_MATCH = "NO MATCH"


@dataclass
class MatchResult:
    """Detailed score result of evaluating an audio candidate against track metadata."""
    confidence_tier: ConfidenceTier
    score: float  # 0.0 to 1.0
    title_score: float
    artist_score: float
    duration_score: float
    explanation: str
    is_auto_eligible: bool


class TrackMatcher:
    """
    Evaluates candidate audio sources against canonical song metadata.
    Computes composite similarity scores and classifies match confidence.
    """

    CLEAN_PATTERNS = [
        re.compile(r"\[\s*official\s*[^\]]*\]", re.I),
        re.compile(r"\(\s*official\s*[^\)]*\)", re.I),
        re.compile(r"\[\s*(?:video|audio|lyrics?|hd|4k|song|full\s*song)[^\]]*\]", re.I),
        re.compile(r"\(\s*(?:video|audio|lyrics?|hd|4k|song|full\s*song)[^\)]*\)", re.I),
        re.compile(r"\(\s*from\s+[\"'].*?[\"']\s*\)", re.I),
        re.compile(r"\(\s*from\s+.*?\s*\)", re.I),
        re.compile(r"\[\s*from\s+.*?\s*\]", re.I),
        re.compile(r"\[\s*\d+k\s*\]", re.I),
        re.compile(r"\b\d+k\b", re.I),
        re.compile(r"\b\d+\s*kbps\b", re.I),
        re.compile(r"\bmasstamilan\b", re.I),
        re.compile(r"\bstar\s*music\b", re.I),
        re.compile(r"\bsony\s*music\b", re.I),
    ]

    def __init__(
        self,
        high_threshold: float = 0.82,
        medium_threshold: float = 0.60,
    ):
        self.high_threshold = high_threshold
        self.medium_threshold = medium_threshold

    @classmethod
    def clean_title(cls, text: str) -> str:
        """Strip noise descriptors like (Official Video), [4K], etc."""
        if not text:
            return ""
        s = text
        for pat in cls.CLEAN_PATTERNS:
            s = pat.sub("", s)
        # Remove symbols and excessive whitespace
        s = re.sub(r"[^\w\s]", " ", s)
        return " ".join(s.lower().split())

    @classmethod
    def string_similarity(cls, target: str, candidate: str) -> float:
        """Normalized string similarity using SequenceMatcher and token containment."""
        c_tar = cls.clean_title(target)
        c_cand = cls.clean_title(candidate)
        if not c_tar or not c_cand:
            return 0.0
        if c_tar == c_cand:
            return 1.0

        # Substring containment bonus (e.g. target title contained in candidate title)
        if c_tar in c_cand:
            return 0.95

        seq_ratio = SequenceMatcher(None, c_tar, c_cand).ratio()

        t_tar = set(c_tar.split())
        t_cand = set(c_cand.split())
        if t_tar and t_cand:
            containment = len(t_tar & t_cand) / len(t_tar)
            jaccard = len(t_tar & t_cand) / len(t_tar | t_cand)
            token_ratio = 0.75 * containment + 0.25 * jaccard
        else:
            token_ratio = 0.0

        return max(seq_ratio * 0.4 + token_ratio * 0.6, token_ratio)

    @classmethod
    def duration_similarity(
        cls,
        expected_sec: Optional[int],
        actual_sec: Optional[int],
    ) -> float:
        """
        Evaluate duration closeness.
        """
        if expected_sec is None or actual_sec is None or expected_sec <= 0 or actual_sec <= 0:
            return 0.70

        delta = abs(expected_sec - actual_sec)
        if delta <= 5:
            return 1.0
        elif delta <= 15:
            return 0.85
        elif delta <= 30:
            return 0.60
        elif delta <= 60:
            return 0.30
        else:
            return 0.05

    def evaluate(
        self,
        target_title: str,
        target_artist: Optional[str],
        target_duration: Optional[int],
        candidate_title: str,
        candidate_uploader: Optional[str] = None,
        candidate_duration: Optional[int] = None,
        candidate_quality_kbps: Optional[int] = None,
    ) -> MatchResult:
        """
        Calculate composite match score and classify confidence tier.
        """
        title_score = self.string_similarity(target_title, candidate_title)

        # Artist score
        if target_artist and (candidate_uploader or candidate_title):
            c_artist = self.clean_title(target_artist)
            c_up = self.clean_title(candidate_uploader or "")
            c_cand_title = self.clean_title(candidate_title)

            if c_artist in c_up or c_artist in c_cand_title:
                artist_score = 1.0
            else:
                a_tokens = set(c_artist.split())
                all_cand_tokens = set(c_up.split()) | set(c_cand_title.split())
                if a_tokens and (a_tokens & all_cand_tokens):
                    artist_score = len(a_tokens & all_cand_tokens) / len(a_tokens)
                else:
                    artist_score = 0.50
        else:
            artist_score = 0.75

        duration_score = self.duration_similarity(target_duration, candidate_duration)

        # Composite score
        # Title (45%), Artist (30%), Duration (25%)
        composite = (0.45 * title_score) + (0.30 * artist_score) + (0.25 * duration_score)

        # Penalize if duration is drastically off (>90s)
        if target_duration and candidate_duration and abs(target_duration - candidate_duration) > 90:
            composite *= 0.40

        # Determine Tier
        if composite >= self.high_threshold:
            tier = ConfidenceTier.HIGH
            auto_eligible = True
            expl = f"High confidence ({int(composite * 100)}%): title & duration match closely"
        elif composite >= self.medium_threshold:
            tier = ConfidenceTier.MEDIUM
            auto_eligible = False
            expl = f"Medium confidence ({int(composite * 100)}%): review suggested"
        elif composite > 0.30:
            tier = ConfidenceTier.LOW
            auto_eligible = False
            expl = f"Low confidence ({int(composite * 100)}%): possible mismatch"
        else:
            tier = ConfidenceTier.NO_MATCH
            auto_eligible = False
            expl = "No satisfactory audio match found"

        return MatchResult(
            confidence_tier=tier,
            score=round(composite, 3),
            title_score=round(title_score, 3),
            artist_score=round(artist_score, 3),
            duration_score=round(duration_score, 3),
            explanation=expl,
            is_auto_eligible=auto_eligible,
        )
