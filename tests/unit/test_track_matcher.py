"""Unit tests for fuzzy track matching and confidence scoring."""

import pytest
from library.matching.matcher import TrackMatcher, ConfidenceTier, MatchResult


@pytest.mark.unit
def test_exact_match():
    matcher = TrackMatcher()
    res = matcher.evaluate(
        target_title="Arabic Kuthu",
        target_artist="Anirudh Ravichander",
        target_duration=280,
        candidate_title="Arabic Kuthu",
        candidate_uploader="Anirudh Ravichander",
        candidate_duration=280,
    )
    assert res.confidence_tier == ConfidenceTier.HIGH
    assert res.score >= 0.85


@pytest.mark.unit
def test_fuzzy_match_with_descriptors():
    matcher = TrackMatcher()
    res = matcher.evaluate(
        target_title="Vaathi Coming",
        target_artist="Anirudh",
        target_duration=230,
        candidate_title="Vaathi Coming (Master) [Official Video] 320Kbps MassTamilan",
        candidate_uploader="Sony Music South",
        candidate_duration=232,
    )
    assert res.confidence_tier in (ConfidenceTier.HIGH, ConfidenceTier.MEDIUM)
    assert res.score >= 0.70


@pytest.mark.unit
def test_mismatch_low_score():
    matcher = TrackMatcher()
    res = matcher.evaluate(
        target_title="Arabic Kuthu",
        target_artist="Anirudh",
        target_duration=280,
        candidate_title="Why This Kolaveri Di Official Video",
        candidate_uploader="Sony Music",
        candidate_duration=250,
    )
    assert res.confidence_tier in (ConfidenceTier.LOW, ConfidenceTier.NO_MATCH)
    assert res.score < 0.60
