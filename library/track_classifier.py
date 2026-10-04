"""
Soundtrack Track Classification and Variant Detection Module.

Classifies soundtrack entries into:
1. PRIMARY: Official soundtrack song, eligible for default Download Missing and main tracklist.
2. ALTERNATE: Legitimate alternate versions (Male/Female version, Reprise, Acoustic, Remix, etc.)
   associated with a canonical base song.
3. NON_PRIMARY: Utility audio snippets (ringtones, teasers, karaoke, caller tunes, dialogue snippets)
   excluded from default soundtrack counts and download missing flows.
"""

from enum import Enum
import re
from typing import Any, Dict, List, Optional, Tuple


class TrackClassification(str, Enum):
    PRIMARY = "PRIMARY"
    ALTERNATE = "ALTERNATE"
    NON_PRIMARY = "NON_PRIMARY"


# Regex patterns for utility/non-primary audio snippets
_NON_PRIMARY_PATTERNS = [
    re.compile(r"\b(ring\s*tone|short\s*tone|notification\s*tone|caller\s*tune|mobile\s*tone)\b", re.IGNORECASE),
    re.compile(r"\b(teaser(\s*audio|\s*snippet|\s*cut)?|trailer\s*(audio|snippet|cut)?|promo(\s*(audio|snippet|cut|track|dialogue))?)\b", re.IGNORECASE),
    re.compile(r"\b(dialogue(\s*(promo|snippet|track|cut))?|punch\s*dialogue)\b", re.IGNORECASE),
    re.compile(r"\b(karaoke|minus\s*one|backing\s*track)\b", re.IGNORECASE),
    re.compile(r"\b(bgm\s*(snippet|cut|ringtone)|whistle\s*ringtone)\b", re.IGNORECASE),
]

# Regex patterns for legitimate alternate versions / variants
_ALTERNATE_PATTERNS = [
    (re.compile(r"[\(\[\-]\s*(female\s*version|female)\s*[\)\]]?", re.IGNORECASE), "Female Version"),
    (re.compile(r"[\(\[\-]\s*(male\s*version|male)\s*[\)\]]?", re.IGNORECASE), "Male Version"),
    (re.compile(r"[\(\[\-]\s*(reprise)\s*[\)\]]?", re.IGNORECASE), "Reprise"),
    (re.compile(r"[\(\[\-]\s*(acoustic(\s*version)?|unplugged)\s*[\)\]]?", re.IGNORECASE), "Acoustic Version"),
    (re.compile(r"[\(\[\-]\s*(live(\s*version)?)\s*[\)\]]?", re.IGNORECASE), "Live Version"),
    (re.compile(r"[\(\[\-]\s*(remix|edm\s*remix|club\s*mix|extended\s*mix|dj\s*remix)\s*[\)\]]?", re.IGNORECASE), "Remix"),
    (re.compile(r"[\(\[\-]\s*(alternate\s*version|alternate\s*take)\s*[\)\]]?", re.IGNORECASE), "Alternate Version"),
    (re.compile(r"[\(\[\-]\s*(radio\s*edit|radio\s*version)\s*[\)\]]?", re.IGNORECASE), "Radio Edit"),
    (re.compile(r"[\(\[\-]\s*(slowed\s*(and|\+)?\s*reverb)\s*[\)\]]?", re.IGNORECASE), "Slowed + Reverb"),
    (re.compile(r"[\(\[\-]\s*(version\s*[12345]|\bpt\.?\s*[12345]\b|part\s*[12345])\s*[\)\]]?", re.IGNORECASE), "Version Variation"),
]

# Descriptor suffixes often appended to indie/film tracks (e.g. "Rathinamo - Saurav Srisan")
_ARTIST_OR_FILM_DESCRIPTOR_RE = re.compile(
    r"\s*(?:\(from\s+[^)]+\)|\(from\s+[“\"][^”\"]+[”\"]\)|-\s*[A-Za-z0-9\s&,]+)\s*$",
    re.IGNORECASE,
)


def extract_base_title(title: str) -> str:
    """
    Extract canonical base title by stripping version/descriptor suffixes.
    e.g. 'Rathinamo (Female Version)' -> 'Rathinamo'
         'Rathinamo Female Version' -> 'Rathinamo'
         'Aasai Varame (Reprise)' -> 'Aasai Varame'
         'Aasai Varame (From Anbil Avan)' -> 'Aasai Varame'
    """
    if not title:
        return ""
    cleaned = title.strip()

    # Strip alternate patterns
    for pat, _ in _ALTERNATE_PATTERNS:
        cleaned = pat.sub("", cleaned).strip()

    # Strip inline words like "Female Version" or "Male Version" even without parentheses
    cleaned = re.sub(r"\s+\b(female\s*version|male\s*version|reprise|remix|acoustic)\b", "", cleaned, flags=re.IGNORECASE).strip()

    # Strip (From "Movie") or (From Movie)
    cleaned = re.sub(r"\s*\((?:from\s+[^)]+|original\s+soundtrack)\)", "", cleaned, flags=re.IGNORECASE).strip()

    # Strip trailing dash descriptors (e.g., "- Saurav Srisan" if preceded by a title)
    dash_match = re.search(r"^(.*?)\s*-\s*[A-Za-z\s]+$", cleaned)
    if dash_match and len(dash_match.group(1).strip()) >= 3:
        cleaned = dash_match.group(1).strip()

    return cleaned or title.strip()


def classify_track_single(
    title: str,
    duration_sec: Optional[int] = None,
    existing_base_titles: Optional[set] = None,
) -> Tuple[TrackClassification, Optional[str], str]:
    """
    Classify a single track.
    Returns:
        (classification, variant_label, base_title)
    """
    t_clean = (title or "").strip()
    base_title = extract_base_title(t_clean)
    existing_bases = existing_base_titles or set()

    # 1. Non-primary checks
    for pat in _NON_PRIMARY_PATTERNS:
        if pat.search(t_clean):
            return TrackClassification.NON_PRIMARY, "Non-Primary Snippet", base_title

    # Short duration snippets (< 35s) with keyword indications
    if duration_sec is not None and 0 < duration_sec < 35:
        if re.search(r"\b(cut|snippet|tone|short|teaser|dialogue|bgm)\b", t_clean, re.IGNORECASE):
            return TrackClassification.NON_PRIMARY, "Short Audio Snippet", base_title

    # Instrumental check:
    # Only flag as non-primary utility if it's an explicit Karaoke / Minus One / Backing Track,
    # OR if there is an existing primary vocal song with the exact same base title
    # (i.e. 'Song A' exists and 'Song A (Instrumental)' also exists as a karaoke duplicate).
    # If the track is an original theme/score (e.g. 'Theme of Passion', 'Overture'), keep it PRIMARY!
    if re.search(r"\b(karaoke|minus\s*one|backing\s*track)\b", t_clean, re.IGNORECASE):
        return TrackClassification.NON_PRIMARY, "Karaoke / Backing Track", base_title

    is_instrumental = bool(re.search(r"\b(instrumental)\b", t_clean, re.IGNORECASE))
    if is_instrumental:
        # Check if there is another non-instrumental track with this base title
        has_vocal_counterpart = False
        for eb in existing_bases:
            if eb == base_title.lower() and eb != t_clean.lower():
                has_vocal_counterpart = True
                break
        if has_vocal_counterpart:
            return TrackClassification.NON_PRIMARY, "Instrumental Duplicate", base_title
        # Otherwise, this is a genuine official instrumental soundtrack theme
        return TrackClassification.PRIMARY, None, base_title

    # 2. Alternate version checks
    for pat, label in _ALTERNATE_PATTERNS:
        if pat.search(t_clean):
            return TrackClassification.ALTERNATE, label, base_title

    # Inline text match (e.g. "Rathinamo Female Version" without parens)
    if re.search(r"\b(female\s*version|female)\b", t_clean, re.IGNORECASE):
        return TrackClassification.ALTERNATE, "Female Version", base_title
    if re.search(r"\b(male\s*version|male)\b", t_clean, re.IGNORECASE):
        return TrackClassification.ALTERNATE, "Male Version", base_title
    if re.search(r"\b(reprise)\b", t_clean, re.IGNORECASE):
        return TrackClassification.ALTERNATE, "Reprise", base_title
    if re.search(r"\b(remix)\b", t_clean, re.IGNORECASE):
        return TrackClassification.ALTERNATE, "Remix", base_title
    if re.search(r"\b(acoustic)\b", t_clean, re.IGNORECASE):
        return TrackClassification.ALTERNATE, "Acoustic Version", base_title

    # If the title ends with a dash and performer descriptor (e.g. "Rathinamo - Saurav Srisan")
    # AND the base title ("Rathinamo") already exists in this movie:
    if base_title.lower() in existing_bases and t_clean.lower() != base_title.lower():
        # Check if descriptor is present
        if "-" in t_clean or "(" in t_clean:
            return TrackClassification.ALTERNATE, "Performer Variant", base_title
        # Even without dash, if exact base title exists and this is longer variation
        return TrackClassification.ALTERNATE, "Alternate Version", base_title

    # 3. Primary official soundtrack song
    return TrackClassification.PRIMARY, None, base_title


def classify_movie_soundtrack(songs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Classify a complete set of songs for a movie.
    Identifies primary songs, groups alternate versions, and isolates non-primary audio.
    """
    primary_songs = []
    alternate_songs = []
    non_primary_songs = []

    # First pass: collect clean base titles from shortest/standard titles
    base_titles = set()
    for s in songs:
        t = s.get("title", "")
        b = extract_base_title(t)
        if b:
            base_titles.add(b.lower())

    seen_primary_bases = set()

    for s in songs:
        s_copy = dict(s)
        t = s_copy.get("title", "")
        dur = s_copy.get("duration_seconds")
        cls, variant_tag, base = classify_track_single(t, dur, base_titles)

        # If it was marked PRIMARY, but we already have an identical primary base song in this movie,
        # reclassify this duplicate/variant as ALTERNATE so it doesn't inflate the official song list!
        if cls == TrackClassification.PRIMARY:
            b_norm = base.lower()
            if b_norm in seen_primary_bases:
                cls = TrackClassification.ALTERNATE
                variant_tag = "Alternate Take / Release"
            else:
                seen_primary_bases.add(b_norm)

        s_copy["classification"] = cls.value
        s_copy["variant_type"] = variant_tag
        s_copy["base_title"] = base

        if cls == TrackClassification.PRIMARY:
            primary_songs.append(s_copy)
        elif cls == TrackClassification.ALTERNATE:
            alternate_songs.append(s_copy)
        else:
            non_primary_songs.append(s_copy)

    # Sort primary songs by track_number where available
    primary_songs.sort(key=lambda x: (x.get("track_number") or 999, x.get("title", "")))

    return {
        "primary_songs": primary_songs,
        "alternate_songs": alternate_songs,
        "non_primary_songs": non_primary_songs,
        "all_songs": primary_songs + alternate_songs + non_primary_songs,
        "stats": {
            "total_primary": len(primary_songs),
            "total_alternate": len(alternate_songs),
            "total_non_primary": len(non_primary_songs),
            "total_all": len(songs),
        },
    }
