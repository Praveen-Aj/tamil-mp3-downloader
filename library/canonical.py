"""
Canonical identity system for songs.

Provides deterministic song identity based on normalized metadata
to enable cross-category and cross-source deduplication.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Optional, Tuple


def compute_canonical_hash(title: str, artist: str, album: str,
                          year: Optional[int] = None,
                          duration: Optional[int] = None,
                          strip_variants: bool = False) -> str:
    """
    Compute canonical hash for song identity.

    Normalization rules:
    - Case-insensitive
    - Remove extra whitespace and special chars
    - Strip variants only if strip_variants=True (for grouping purposes)
    - Normalize Tamil transliteration (future enhancement)

    Args:
        title: Song title
        artist: Artist name
        album: Album name
        year: Release year (optional)
        duration: Duration in seconds (optional)
        strip_variants: Whether to strip variant suffixes (default False)

    Returns:
        SHA256 hash of canonical metadata
    """
    # Extract base title (remove variant suffixes) only if requested
    if strip_variants:
        base_title = extract_base_title(title)
    else:
        base_title = title

    # Normalize components
    norm_title = normalize_string(base_title)
    norm_artist = normalize_string(artist) if artist else ""
    norm_album = normalize_string(album) if album else ""

    # Create canonical string
    canonical_parts = [norm_title, norm_artist, norm_album]
    if year:
        canonical_parts.append(str(year))
    if duration:
        canonical_parts.append(str(duration))

    canonical_string = "|".join(canonical_parts)

    # SHA256 hash
    return hashlib.sha256(canonical_string.encode('utf-8')).hexdigest()


def extract_base_title(title: str) -> str:
    """
    Remove variant suffixes from title.

    Suffixes that indicate different versions:
    - Remix, Instrumental, Karaoke, Extended, Reprise, Version

    Args:
        title: Original song title

    Returns:
        Base title without variant suffixes
    """
    variant_suffixes = [
        r'\s*-\s*Remix$', r'\s*-\s*Instrumental$', r'\s*-\s*Karaoke$',
        r'\s*-\s*Extended$', r'\s*-\s*Reprise$', r'\s*-\s*Version\s*\d*$',
        r'\s*\(Remix\)$', r'\s*\(Instrumental\)$', r'\s*\(Karaoke\)$',
        r'\s*\(Extended\)$', r'\s*\(Reprise\)$', r'\s*\(Version\s*\d*\)$',
    ]
    base = title
    for suffix in variant_suffixes:
        base = re.sub(suffix, '', base, flags=re.IGNORECASE)
    return base.strip()


def normalize_string(s: str) -> str:
    """
    Normalize string for comparison.

    Normalization steps:
    - Convert to lowercase
    - Remove special characters except spaces
    - Normalize whitespace

    Args:
        s: Input string

    Returns:
        Normalized string
    """
    # Lowercase
    s = s.lower()
    # Remove special chars except spaces and word chars
    s = re.sub(r'[^\w\s]', '', s)
    # Normalize whitespace
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


def normalize_artist_name(name: Optional[str]) -> str:
    """
    Deterministically normalize person / artist names for canonical comparison and deduplication.

    Handles:
    - Formatting variations around initials:
      'A. R. Rahman', 'A.R. Rahman', 'A R Rahman', 'A.R.Rahman', 'a. r. rahman' -> 'a r rahman'
    - Dots, dashes, slashes, and underscores are treated as token separators.
    - Preserves distinct individual identities.
    """
    if not name:
        return ""
    s = name.lower()
    # Replace dots, dashes, underscores, slashes with spaces so initials don't concatenate ('a.r.' -> 'a r ')
    s = re.sub(r'[\.\-_/]', ' ', s)
    # Remove remaining non-word and non-space characters
    s = re.sub(r'[^\w\s]', '', s)
    # Collapse multiple whitespaces
    s = re.sub(r'\s+', ' ', s)
    return s.strip()


@dataclass
class CanonicalIdentity:
    """
    Canonical identity metadata for a song.

    Attributes:
        hash: SHA256 hash of canonical metadata
        title_normalized: Normalized title
        artist_normalized: Normalized artist
        album_normalized: Normalized album
        year: Release year (optional)
        duration_seconds: Duration in seconds (optional)
        title_original: Original title for display
        artist_original: Original artist for display
        album_original: Original album for display
        has_variant: Whether the original title has a variant suffix
    """
    hash: str
    title_normalized: str
    artist_normalized: str
    album_normalized: str
    year: Optional[int] = None
    duration_seconds: Optional[int] = None
    title_original: str = ""
    artist_original: str = ""
    album_original: str = ""
    has_variant: bool = False

    @classmethod
    def from_metadata(cls, title: str, artist: str, album: str,
                     year: Optional[int] = None,
                     duration: Optional[int] = None,
                     strip_variants: bool = False) -> 'CanonicalIdentity':
        """
        Create CanonicalIdentity from raw metadata.

        Args:
            title: Song title
            artist: Artist name
            album: Album name
            year: Release year (optional)
            duration: Duration in seconds (optional)
            strip_variants: Whether to strip variant suffixes (default False)

        Returns:
            CanonicalIdentity instance
        """
        canonical_hash = compute_canonical_hash(title, artist, album, year, duration, strip_variants)
        base_title = extract_base_title(title) if strip_variants else title

        # Check if original title has variant suffix
        has_variant = any(suffix.lower() in title.lower() for suffix in
                         ['remix', 'instrumental', 'karaoke', 'extended', 'reprise', 'version'])

        return cls(
            hash=canonical_hash,
            title_normalized=normalize_string(base_title),
            artist_normalized=normalize_string(artist) if artist else "",
            album_normalized=normalize_string(album) if album else "",
            year=year,
            duration_seconds=duration,
            title_original=title,
            artist_original=artist or "",
            album_original=album or "",
            has_variant=has_variant,
        )

    def matches(self, other: 'CanonicalIdentity', confidence_threshold: float = 0.9) -> bool:
        """
        Check if this identity matches another with high confidence.

        Conservative matching rules:
        - Remix vs original: NO MATCH (unless one has variant suffix)
        - Instrumental vs original: NO MATCH
        - Different years: NO MATCH (unless within 1 year and all else matches)
        - Different artists: NO MATCH (unless featuring variations)

        Args:
            other: Another CanonicalIdentity to compare
            confidence_threshold: Minimum confidence for match (0.0-1.0)

        Returns:
            True if identities match with high confidence
        """
        # Exact hash match is always a match
        if self.hash == other.hash:
            return True

        # Check for variant suffixes - these should NOT match
        has_variant = lambda t: any(suffix.lower() in t.lower() for suffix in
                                   ['remix', 'instrumental', 'karaoke', 'extended', 'reprise', 'version'])

        # If either has a variant suffix, they shouldn't match
        if has_variant(self.title_original) or has_variant(other.title_original):
            return False

        # Year difference check
        if self.year and other.year:
            if abs(self.year - other.year) > 1:
                return False

        # Artist similarity check (basic)
        if self.artist_normalized and other.artist_normalized:
            if self.artist_normalized != other.artist_normalized:
                # Could add fuzzy matching for featuring variations
                return False

        # Title similarity check
        if self.title_normalized != other.title_normalized:
            return False

        # Album similarity check
        if self.album_normalized and other.album_normalized:
            if self.album_normalized != other.album_normalized:
                return False

        return True

    def __str__(self) -> str:
        """String representation for debugging."""
        parts = [self.title_original]
        if self.artist_original:
            parts.append(f"by {self.artist_original}")
        if self.album_original:
            parts.append(f"from {self.album_original}")
        if self.year:
            parts.append(f"({self.year})")
        return " ".join(parts)


class Canonicalizer:
    """Helper wrapper for computing canonical hashes and normalized strings."""

    @staticmethod
    def compute_hash(
        title: str,
        artist: str = "",
        album: str = "",
        duration_seconds: Optional[int] = None,
        year: Optional[int] = None,
    ) -> str:
        return compute_canonical_hash(
            title=title,
            artist=artist,
            album=album,
            duration=duration_seconds,
            year=year,
        )

    @staticmethod
    def normalize_text(text: str) -> str:
        return normalize_string(text)
