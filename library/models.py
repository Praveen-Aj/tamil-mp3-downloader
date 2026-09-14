"""
Data models for the library system.

These models represent the persistent state in the SQLite database
and provide a clean interface for library operations.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional


class SongState(Enum):
    """Library state of a song."""
    NEW = "NEW"
    OWNED = "OWNED"
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    MISSING = "MISSING"
    DUPLICATE = "DUPLICATE"


class DownloadState(Enum):
    """State of a download operation."""
    PLANNED = "PLANNED"
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


@dataclass
class LibraryLocation:
    """
    Represents a music library directory.

    Attributes:
        id: Database ID
        path: Filesystem path
        name: Display name
        is_primary: Whether this is the primary library
        created_at: When this location was added
        last_scanned_at: Last time this location was scanned
    """
    id: Optional[int] = None
    path: str = ""
    name: str = ""
    is_primary: bool = False
    created_at: Optional[datetime] = None
    last_scanned_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'LibraryLocation':
        """Create LibraryLocation from database row."""
        return cls(
            id=row['id'],
            path=row['path'],
            name=row['name'],
            is_primary=bool(row['is_primary']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,  # noqa: E501
            last_scanned_at=datetime.fromisoformat(row['last_scanned_at']) if row['last_scanned_at'] else None,  # noqa: E501
        )


@dataclass
class LibrarySong:
    """
    Represents a canonical song in the library.

    Attributes:
        id: Database ID
        canonical_hash: SHA256 hash of canonical metadata
        title_normalized: Normalized title for comparison
        artist_normalized: Normalized artist for comparison
        album_normalized: Normalized album for comparison
        year: Release year
        duration_seconds: Duration in seconds
        title: Original title for display
        artist: Original artist for display
        album: Original album for display
        state: Library state (NEW, OWNED, etc.)
        quality_kbps: Best quality available
        file_size_bytes: File size in bytes
        library_location_id: ID of library location
        file_path: Path to file
        first_discovered_at: When first discovered
        last_seen_at: When last seen
        last_played_at: When last played
        play_count: Number of times played
    """
    id: Optional[int] = None
    canonical_hash: str = ""
    title_normalized: str = ""
    artist_normalized: str = ""
    album_normalized: str = ""
    year: Optional[int] = None
    duration_seconds: Optional[int] = None
    title: str = ""
    artist: Optional[str] = None
    album: Optional[str] = None
    state: SongState = SongState.NEW
    quality_kbps: Optional[int] = None
    file_size_bytes: Optional[int] = None
    library_location_id: Optional[int] = None
    file_path: Optional[str] = None
    first_discovered_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    last_played_at: Optional[datetime] = None
    play_count: int = 0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'LibrarySong':
        """Create LibrarySong from database row."""
        return cls(
            id=row['id'],
            canonical_hash=row['canonical_hash'],
            title_normalized=row['title_normalized'],
            artist_normalized=row['artist_normalized'],
            album_normalized=row['album_normalized'],
            year=row['year'],
            duration_seconds=row['duration_seconds'],
            title=row['title'],
            artist=row['artist'],
            album=row['album'],
            state=SongState(row['state']) if row['state'] else SongState.NEW,
            quality_kbps=row['quality_kbps'],
            file_size_bytes=row['file_size_bytes'],
            library_location_id=row['library_location_id'],
            file_path=row['file_path'],
            first_discovered_at=datetime.fromisoformat(row['first_discovered_at']) if row['first_discovered_at'] else None,  # noqa: E501
            last_seen_at=datetime.fromisoformat(row['last_seen_at']) if row['last_seen_at'] else None,  # noqa: E501
            last_played_at=datetime.fromisoformat(row['last_played_at']) if row['last_played_at'] else None,  # noqa: E501
            play_count=row['play_count'],
        )

    @property
    def is_owned(self) -> bool:
        """Check if song is owned (downloaded)."""
        return self.state == SongState.OWNED

    @property
    def is_downloading(self) -> bool:
        """Check if song is currently downloading."""
        return self.state == SongState.DOWNLOADING

    @property
    def display_name(self) -> str:
        """Get display name with artist."""
        if self.artist:
            return f"{self.title} - {self.artist}"
        return self.title


@dataclass
class SongSource:
    """
    Represents a source variant for a canonical song.

    Attributes:
        id: Database ID
        song_id: ID of the canonical song
        source_name: Name of the source (isaimini, masstamilan, etc.)
        source_url: URL of the source
        download_reference: Persistent source-specific download descriptor (e.g. data-path)
        quality_kbps: Quality in kbps
        file_size_bytes: File size in bytes
        file_type: File type (mp3, zip, m4a, etc.)
        metadata_complete: Whether metadata is complete
        is_available: Whether source is currently available
        availability_last_checked: When availability was last checked
        reliability_score: 0.0-1.0 reliability score
        discovered_at: When this source was discovered
    """
    id: Optional[int] = None
    song_id: Optional[int] = None
    source_name: str = ""
    source_url: str = ""
    download_reference: Optional[str] = None
    quality_kbps: Optional[int] = None
    file_size_bytes: Optional[int] = None
    file_type: Optional[str] = None
    metadata_complete: bool = False
    is_available: bool = True
    availability_last_checked: Optional[datetime] = None
    reliability_score: float = 1.0
    discovered_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'SongSource':
        """Create SongSource from database row."""
        keys = row.keys() if hasattr(row, 'keys') else []
        return cls(
            id=row['id'],
            song_id=row['song_id'],
            source_name=row['source_name'],
            source_url=row['source_url'],
            download_reference=row['download_reference'] if 'download_reference' in keys else None,
            quality_kbps=row['quality_kbps'],
            file_size_bytes=row['file_size_bytes'],
            file_type=row['file_type'],
            metadata_complete=bool(row['metadata_complete']),
            is_available=bool(row['is_available']),
            availability_last_checked=datetime.fromisoformat(row['availability_last_checked']) if row['availability_last_checked'] else None,  # noqa: E501
            reliability_score=row['reliability_score'],
            discovered_at=datetime.fromisoformat(row['discovered_at']) if row['discovered_at'] else None,  # noqa: E501
        )

    @property
    def quality_str(self) -> str:
        """Get quality as string."""
        if self.quality_kbps:
            return f"{self.quality_kbps}kbps"
        return "Unknown"

    @property
    def size_str(self) -> str:
        """Get size as human-readable string."""
        if self.file_size_bytes:
            mb = self.file_size_bytes / (1024 * 1024)
            return f"{mb:.1f} MB"
        return "Unknown"


@dataclass
class Download:
    """
    Represents a download operation.

    Attributes:
        id: Database ID
        song_id: ID of the canonical song
        song_source_id: ID of the source used
        planned_at: When download was planned
        queued_at: When download was queued
        started_at: When download started
        completed_at: When download completed
        failed_at: When download failed
        library_location_id: ID of library location
        output_path: Path where file was saved
        file_size_bytes: Size of downloaded file
        download_speed_bps: Download speed in bytes per second
        state: Download state
        error_message: Error message if failed
        retry_count: Number of retries
        was_upgrade: Whether this was a quality upgrade
        previous_file_path: Path to previous file if upgrade
        previous_quality_kbps: Quality of previous file if upgrade
    """
    id: Optional[int] = None
    song_id: Optional[int] = None
    song_source_id: Optional[int] = None
    planned_at: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    library_location_id: Optional[int] = None
    output_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    download_speed_bps: Optional[float] = None
    state: DownloadState = DownloadState.PLANNED
    error_message: Optional[str] = None
    retry_count: int = 0
    was_upgrade: bool = False
    previous_file_path: Optional[str] = None
    previous_quality_kbps: Optional[int] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'Download':
        """Create Download from database row."""
        return cls(
            id=row['id'],
            song_id=row['song_id'],
            song_source_id=row['song_source_id'],
            planned_at=datetime.fromisoformat(row['planned_at']) if row['planned_at'] else None,  # noqa: E501
            queued_at=datetime.fromisoformat(row['queued_at']) if row['queued_at'] else None,  # noqa: E501
            started_at=datetime.fromisoformat(row['started_at']) if row['started_at'] else None,  # noqa: E501
            completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,  # noqa: E501
            failed_at=datetime.fromisoformat(row['failed_at']) if row['failed_at'] else None,  # noqa: E501
            library_location_id=row['library_location_id'],
            output_path=row['output_path'],
            file_size_bytes=row['file_size_bytes'],
            download_speed_bps=row['download_speed_bps'],
            state=DownloadState(row['state']),
            error_message=row['error_message'],
            retry_count=row['retry_count'],
            was_upgrade=bool(row['was_upgrade']),
            previous_file_path=row['previous_file_path'],
            previous_quality_kbps=row['previous_quality_kbps'],
        )

    @property
    def attempts(self) -> int:
        """Get number of download attempts (1 + retries)."""
        return self.retry_count + 1

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get download duration in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def is_complete(self) -> bool:
        """Check if download completed successfully."""
        return self.state == DownloadState.COMPLETED

    @property
    def is_failed(self) -> bool:
        """Check if download failed."""
        return self.state == DownloadState.FAILED


@dataclass
class DiscoveryContext:
    """
    Represents discovery context for a song.

    Attributes:
        id: Database ID
        song_id: ID of the canonical song
        source_name: Name of the source
        category: Category where discovered
        album_name: Album name where discovered
        album_url: Album URL where discovered
        discovered_at: When discovered
    """
    id: Optional[int] = None
    song_id: Optional[int] = None
    source_name: str = ""
    category: Optional[str] = None
    album_name: Optional[str] = None
    album_url: Optional[str] = None
    discovered_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'DiscoveryContext':
        """Create DiscoveryContext from database row."""
        return cls(
            id=row['id'],
            song_id=row['song_id'],
            source_name=row['source_name'],
            category=row['category'],
            album_name=row['album_name'],
            album_url=row['album_url'],
            discovered_at=datetime.fromisoformat(row['discovered_at']) if row['discovered_at'] else None,  # noqa: E501
        )


class JobStatus(Enum):
    """Status of an import job."""
    ANALYZING = "ANALYZING"
    READY = "READY"
    IN_PROGRESS = "IN_PROGRESS"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ItemState(Enum):
    """State of a track within an import job."""
    OWNED = "OWNED"
    READY = "READY"
    DOWNLOADING = "DOWNLOADING"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NO_SOURCE = "NO_SOURCE"
    FAILED = "FAILED"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SKIPPED = "SKIPPED"


@dataclass
class ImportJob:
    """
    Represents a persistent URL or playlist import job.
    """
    id: str
    url: str
    platform: str
    content_type: str
    title: str
    artist: Optional[str] = None
    total_tracks: int = 0
    artwork_url: Optional[str] = None
    status: JobStatus = JobStatus.READY
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'ImportJob':
        """Create ImportJob from database row."""
        return cls(
            id=row['id'],
            url=row['url'],
            platform=row['platform'],
            content_type=row['content_type'],
            title=row['title'],
            artist=row['artist'] if 'artist' in row.keys() else None,
            total_tracks=row['total_tracks'],
            artwork_url=row['artwork_url'] if 'artwork_url' in row.keys() else None,
            status=JobStatus(row['status']),
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )


@dataclass
class ImportJobItem:
    """
    Represents a single track within an import job.
    """
    id: Optional[int] = None
    job_id: str = ""
    track_index: int = 0
    title: str = ""
    artist: Optional[str] = None
    album: Optional[str] = None
    duration_seconds: Optional[int] = None
    state: ItemState = ItemState.READY
    selected_provider: Optional[str] = None
    selected_source_url: Optional[str] = None
    match_confidence: float = 0.0
    match_explanation: Optional[str] = None
    error_message: Optional[str] = None
    download_id: Optional[int] = None
    canonical_song_id: Optional[int] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'ImportJobItem':
        """Create ImportJobItem from database row."""
        return cls(
            id=row['id'],
            job_id=row['job_id'],
            track_index=row['track_index'],
            title=row['title'],
            artist=row['artist'],
            album=row['album'],
            duration_seconds=row['duration_seconds'],
            state=ItemState(row['state']),
            selected_provider=row['selected_provider'],
            selected_source_url=row['selected_source_url'],
            match_confidence=float(row['match_confidence'] or 0.0),
            match_explanation=row['match_explanation'],
            error_message=row['error_message'],
            download_id=row['download_id'],
            canonical_song_id=row['canonical_song_id'] if 'canonical_song_id' in row.keys() else None,
        )
