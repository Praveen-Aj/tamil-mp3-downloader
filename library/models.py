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
    def bitrate_kbps(self) -> Optional[int]:
        """Alias for quality_kbps."""
        return self.quality_kbps

    @property
    def source_site(self) -> Optional[str]:
        """Default or source site name."""
        return getattr(self, "_source_site", "Library")

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

    @property
    def filename(self) -> Optional[str]:
        if self.output_path:
            import os
            return os.path.basename(self.output_path)
        return None

    @property
    def destination_path(self) -> Optional[str]:
        return self.output_path

    @property
    def source_name(self) -> str:
        return getattr(self, "_source_name", "Audio Stream")


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

    @property
    def track_count(self) -> int:
        return self.total_tracks


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


# ==============================================================================
# V5.1 Multi-Dimensional Music Discovery & Personal Library Models
# ==============================================================================

@dataclass
class Movie:
    """
    Represents a Tamil movie in the discovery catalog.
    """
    id: Optional[int] = None
    title: str = ""
    title_normalized: str = ""
    year: Optional[int] = None
    director: Optional[str] = None
    poster_url: Optional[str] = None
    banner_url: Optional[str] = None
    local_poster_path: Optional[str] = None
    track_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'Movie':
        keys = row.keys() if hasattr(row, 'keys') else []
        return cls(
            id=row['id'],
            title=row['title'],
            title_normalized=row['title_normalized'],
            year=row['year'],
            director=row['director'] if 'director' in keys else None,
            poster_url=row['poster_url'] if 'poster_url' in keys else None,
            banner_url=row['banner_url'] if 'banner_url' in keys else None,
            local_poster_path=row['local_poster_path'] if 'local_poster_path' in keys else None,
            track_count=row['track_count'] if 'track_count' in keys else 0,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )


@dataclass
class Artist:
    """
    Represents an artist, singer, composer, or actor in the music directory.
    """
    id: Optional[int] = None
    name: str = ""
    name_normalized: str = ""
    role: str = "artist"
    photo_url: Optional[str] = None
    local_photo_path: Optional[str] = None
    bio: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'Artist':
        keys = row.keys() if hasattr(row, 'keys') else []
        return cls(
            id=row['id'],
            name=row['name'],
            name_normalized=row['name_normalized'],
            role=row['role'] if 'role' in keys else 'artist',
            photo_url=row['photo_url'] if 'photo_url' in keys else None,
            local_photo_path=row['local_photo_path'] if 'local_photo_path' in keys else None,
            bio=row['bio'] if 'bio' in keys else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )


@dataclass
class MovieActor:
    """Join record linking a movie to an actor."""
    movie_id: int = 0
    actor_id: int = 0
    character_name: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'MovieActor':
        keys = row.keys() if hasattr(row, 'keys') else []
        return cls(
            movie_id=row['movie_id'],
            actor_id=row['actor_id'],
            character_name=row['character_name'] if 'character_name' in keys else None,
        )


@dataclass
class MovieComposer:
    """Join record linking a movie to a music director/composer."""
    movie_id: int = 0
    composer_id: int = 0

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'MovieComposer':
        return cls(
            movie_id=row['movie_id'],
            composer_id=row['composer_id'],
        )


@dataclass
class SongArtist:
    """Join record linking a canonical song to an artist with role."""
    song_id: int = 0
    artist_id: int = 0
    role: str = "singer"

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'SongArtist':
        keys = row.keys() if hasattr(row, 'keys') else []
        return cls(
            song_id=row['song_id'],
            artist_id=row['artist_id'],
            role=row['role'] if 'role' in keys else 'singer',
        )


@dataclass
class SongMovie:
    """Join record linking a canonical song to a movie."""
    song_id: int = 0
    movie_id: int = 0
    track_number: Optional[int] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'SongMovie':
        keys = row.keys() if hasattr(row, 'keys') else []
        return cls(
            song_id=row['song_id'],
            movie_id=row['movie_id'],
            track_number=row['track_number'] if 'track_number' in keys else None,
        )


@dataclass
class UserSongMetadata:
    """User-owned metadata: personal ratings (1-5), favorites, notes, and tags."""
    song_id: int = 0
    rating: Optional[int] = None
    is_favorite: bool = False
    notes: Optional[str] = None
    tags: Optional[str] = None
    favorited_at: Optional[datetime] = None
    last_rated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'UserSongMetadata':
        keys = row.keys() if hasattr(row, 'keys') else []
        return cls(
            song_id=row['song_id'],
            rating=row['rating'],
            is_favorite=bool(row['is_favorite']),
            notes=row['notes'] if 'notes' in keys else None,
            tags=row['tags'] if 'tags' in keys else None,
            favorited_at=datetime.fromisoformat(row['favorited_at']) if row['favorited_at'] else None,
            last_rated_at=datetime.fromisoformat(row['last_rated_at']) if row['last_rated_at'] else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )


@dataclass
class Playlist:
    """User-defined playlist or smart collection."""
    id: Optional[int] = None
    name: str = ""
    description: Optional[str] = None
    cover_url: Optional[str] = None
    is_smart: bool = False
    smart_criteria_json: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'Playlist':
        keys = row.keys() if hasattr(row, 'keys') else []
        return cls(
            id=row['id'],
            name=row['name'],
            description=row['description'] if 'description' in keys else None,
            cover_url=row['cover_url'] if 'cover_url' in keys else None,
            is_smart=bool(row['is_smart']),
            smart_criteria_json=row['smart_criteria_json'] if 'smart_criteria_json' in keys else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
            updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None,
        )


@dataclass
class PlaylistItem:
    """An individual song entry inside a playlist."""
    id: Optional[int] = None
    playlist_id: int = 0
    song_id: int = 0
    position: int = 0
    added_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'PlaylistItem':
        return cls(
            id=row['id'],
            playlist_id=row['playlist_id'],
            song_id=row['song_id'],
            position=row['position'],
            added_at=datetime.fromisoformat(row['added_at']) if row['added_at'] else None,
        )


@dataclass
class Chart:
    """Curated chart or ranking feed."""
    id: str = ""
    title: str = ""
    chart_type: str = ""
    provider_name: str = ""
    snapshot_date: Optional[datetime] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'Chart':
        return cls(
            id=row['id'],
            title=row['title'],
            chart_type=row['chart_type'],
            provider_name=row['provider_name'],
            snapshot_date=datetime.fromisoformat(row['snapshot_date']) if row['snapshot_date'] else None,
            created_at=datetime.fromisoformat(row['created_at']) if row['created_at'] else None,
        )


@dataclass
class ChartEntry:
    """An individual ranked song entry within a chart snapshot."""
    id: Optional[int] = None
    chart_id: str = ""
    rank: int = 0
    previous_rank: Optional[int] = None
    song_id: Optional[int] = None
    raw_title: str = ""
    raw_artist: Optional[str] = None
    raw_movie: Optional[str] = None

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> 'ChartEntry':
        keys = row.keys() if hasattr(row, 'keys') else []
        return cls(
            id=row['id'],
            chart_id=row['chart_id'],
            rank=row['rank'],
            previous_rank=row['previous_rank'] if 'previous_rank' in keys else None,
            song_id=row['song_id'] if 'song_id' in keys else None,
            raw_title=row['raw_title'],
            raw_artist=row['raw_artist'] if 'raw_artist' in keys else None,
            raw_movie=row['raw_movie'] if 'raw_movie' in keys else None,
        )
