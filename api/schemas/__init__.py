"""
API Pydantic Schemas Package.
"""

from api.schemas.common import ApiResponse, PaginatedResponse, PaginationParams
from api.schemas.song import SongResponse, SongFilterParams, SongRatingUpdate, SongFavoriteUpdate
from api.schemas.movie import MovieResponse, MovieDetailResponse
from api.schemas.artist import ArtistResponse, ArtistDetailResponse
from api.schemas.chart import ChartResponse, ChartDetailResponse, ChartEntryResponse
from api.schemas.playlist import (
    PlaylistResponse, PlaylistDetailResponse, PlaylistItemResponse,
    PlaylistCreate, PlaylistUpdate, PlaylistItemAdd, PlaylistItemMove
)
from api.schemas.download import (
    DownloadItemResponse, DownloadPlanRequest, DownloadPlanResponse,
    DownloadPlanItemResponse, DownloadExecuteRequest
)
from api.schemas.import_job import (
    ImportAnalyzeRequest, ImportAnalyzeResponse, ImportCandidateItem, ImportExecuteRequest
)
from api.schemas.settings import SettingsResponse, SettingsUpdateRequest, DownloadSettings

__all__ = [
    "ApiResponse",
    "PaginatedResponse",
    "PaginationParams",
    "SongResponse",
    "SongFilterParams",
    "SongRatingUpdate",
    "SongFavoriteUpdate",
    "MovieResponse",
    "MovieDetailResponse",
    "ArtistResponse",
    "ArtistDetailResponse",
    "ChartResponse",
    "ChartDetailResponse",
    "ChartEntryResponse",
    "PlaylistResponse",
    "PlaylistDetailResponse",
    "PlaylistItemResponse",
    "PlaylistCreate",
    "PlaylistUpdate",
    "PlaylistItemAdd",
    "PlaylistItemMove",
    "DownloadItemResponse",
    "DownloadPlanRequest",
    "DownloadPlanResponse",
    "DownloadPlanItemResponse",
    "DownloadExecuteRequest",
    "ImportAnalyzeRequest",
    "ImportAnalyzeResponse",
    "ImportCandidateItem",
    "ImportExecuteRequest",
    "SettingsResponse",
    "SettingsUpdateRequest",
    "DownloadSettings",
]
