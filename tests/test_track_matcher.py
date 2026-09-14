"""
Unit tests for TrackMatcher fuzzy matching and confidence scoring.
"""

import pytest
from library.matching.matcher import TrackMatcher, ConfidenceTier


@pytest.fixture
def matcher():
    return TrackMatcher()


def test_clean_title_removes_noise_descriptors(matcher):
    raw = "Arabic Kuthu (From \"Beast\") [Official Video Song] [4K] 320kbps MassTamilan"
    cleaned = matcher.clean_title(raw)
    assert "official" not in cleaned
    assert "video" not in cleaned
    assert "320" not in cleaned
    assert "masstamilan" not in cleaned
    assert "arabic kuthu" in cleaned


def test_exact_match_scores_high_confidence(matcher):
    result = matcher.evaluate(
        target_title="Naa Ready",
        target_artist="Anirudh Ravichander",
        target_duration=248,
        candidate_title="Leo - Naa Ready Official Video | Thalapathy Vijay | Anirudh Ravichander",
        candidate_uploader="Sony Music South",
        candidate_duration=250,
    )

    assert result.confidence_tier == ConfidenceTier.HIGH
    assert result.is_auto_eligible is True
    assert result.score >= 0.80


def test_duration_delta_penalizes_mismatch(matcher):
    # Same title but duration is 10 minutes instead of 3 minutes
    res_correct = matcher.evaluate(
        target_title="Chinna Chinna Aasai",
        target_artist="A.R. Rahman",
        target_duration=295,
        candidate_title="Chinna Chinna Aasai | Roja",
        candidate_uploader="SonyMusicSouthVEVO",
        candidate_duration=297,
    )

    res_long = matcher.evaluate(
        target_title="Chinna Chinna Aasai",
        target_artist="A.R. Rahman",
        target_duration=295,
        candidate_title="Chinna Chinna Aasai 1 Hour Extended Loop",
        candidate_uploader="Fan Channel",
        candidate_duration=3600,
    )

    assert res_correct.score > res_long.score
    assert res_long.confidence_tier in [ConfidenceTier.LOW, ConfidenceTier.NO_MATCH]
    assert res_long.is_auto_eligible is False


def test_low_similarity_scores_no_match(matcher):
    result = matcher.evaluate(
        target_title="Enjoy Enjaami",
        target_artist="Dhee ft. Arivu",
        target_duration=230,
        candidate_title="Totally Unrelated Hindi Remix Song",
        candidate_uploader="RandomDJ",
        candidate_duration=120,
    )

    assert result.confidence_tier in [ConfidenceTier.LOW, ConfidenceTier.NO_MATCH]
    assert result.is_auto_eligible is False
