"""
Songs Router for V6 Web API.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from api.deps import get_service, get_settings
from api.schemas.common import ApiResponse, PaginatedResponse
from api.schemas.song import SongFavoriteUpdate, SongRatingUpdate, SongResponse
from api.streaming import create_audio_stream_response
from library.service import LibraryService
from config.settings import Settings

from library.canonical import clean_song_title
from library.models import SongState

router = APIRouter(prefix="/songs", tags=["Songs"])


def format_song_item(s: Any, service: Optional[LibraryService] = None) -> Dict[str, Any]:
    """Normalize a LibrarySong object or dict to a uniform dictionary with canonical metadata."""
    if isinstance(s, dict):
        sid = s.get("id")
        raw_title = s.get("title", "")
        artist = s.get("artist") or "—"
        album = s.get("album") or "—"
        year = s.get("year")
        raw_state = s.get("state", "NEW")
        quality = s.get("quality_kbps") or s.get("quality")
        file_path = s.get("file_path")
        is_favorite = bool(s.get("is_favorite", False))
        rating = s.get("rating")
        canonical_hash = s.get("canonical_hash", "")
    else:
        sid = s.id
        raw_title = s.title
        artist = getattr(s, "artist", "") or "—"
        album = getattr(s, "album", "") or "—"
        year = getattr(s, "year", None)
        raw_state = s.state.value if hasattr(s.state, "value") else str(s.state)
        quality = getattr(s, "quality_kbps", None) or getattr(s, "quality", None)
        file_path = getattr(s, "file_path", None)
        is_favorite = bool(getattr(s, "is_favorite", False))
        rating = getattr(s, "rating", None)
        canonical_hash = getattr(s, "canonical_hash", "")

    clean_title = clean_song_title(raw_title)
    has_file = bool(file_path and Path(file_path).is_file()) if file_path else False
    is_owned = (raw_state.upper() == "OWNED" or has_file)

    download_state = "NOT_DOWNLOADED"
    can_upgrade = False

    if is_owned:
        download_state = "DOWNLOADED"
        if quality and quality < 320:
            can_upgrade = True
            if service and sid:
                sources = service.db.get_sources_for_song(sid)
                if any((src.quality_kbps or 0) > quality for src in sources):
                    download_state = "UPGRADE_AVAILABLE"
    elif raw_state.upper() == "DOWNLOADING":
        download_state = "DOWNLOADING"
    elif raw_state.upper() == "FAILED":
        download_state = "FAILED"
    else:
        download_state = "NOT_DOWNLOADED"

    return {
        "id": sid,
        "canonical_hash": canonical_hash,
        "title": clean_title,
        "artist": artist,
        "album": album,
        "year": year,
        "state": "OWNED" if is_owned else raw_state,
        "download_state": download_state,
        "can_upgrade": can_upgrade,
        "rating": rating,
        "is_favorite": is_favorite,
        "has_file": has_file,
        "file_path": file_path,
        "quality": quality,
    }


@router.get("", response_model=ApiResponse[PaginatedResponse[Dict[str, Any]]])
def list_songs(
    query: str = Query(default=""),
    state: Optional[str] = Query(default=None),
    year: Optional[int] = Query(default=None),
    source: Optional[str] = Query(default=None),
    quality: Optional[int] = Query(default=None),
    sort_by: str = Query(default="id"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[PaginatedResponse[Dict[str, Any]]]:
    """Fetch paginated library songs with comprehensive search, filters, and sorting."""
    actual_state = state if state and state.upper() != "ALL" else None
    page_data = service.get_library_page(
        page=page,
        page_size=page_size,
        query=query,
        state=actual_state,
        quality=quality,
        source=source,
        sort_by=sort_by,
        ascending=(sort_order.lower() == "asc"),
    )
    raw_songs = page_data.get("songs") or page_data.get("items", [])
    total = page_data.get("total_items") if "total_items" in page_data else page_data.get("total", 0)
    items = [format_song_item(s, service) for s in raw_songs]
    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

    return ApiResponse(
        success=True,
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.post("/download-missing", response_model=ApiResponse[Dict[str, Any]])
def download_all_missing_songs(
    preferred_quality: int = Query(default=320),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Plan and queue background downloads for all missing library songs."""
    service.reconcile_library_files()
    missing_songs = service.get_unowned_songs(limit=100)
    if not missing_songs:
        return ApiResponse(success=True, message="All songs are already downloaded", data={"queued_count": 0})

    plan = service.planner.plan_downloads_for_songs(missing_songs, preferred_quality=preferred_quality)
    queued_count = service.execute_download_plan(plan)
    return ApiResponse(
        success=True,
        message=f"Queued {queued_count} missing songs for download",
        data={"queued_count": queued_count},
    )


@router.get("/downloaded", response_model=ApiResponse[PaginatedResponse[Dict[str, Any]]])
def list_downloaded_songs(
    query: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[PaginatedResponse[Dict[str, Any]]]:
    """Fetch paginated downloaded songs verified against the physical filesystem."""
    all_downloaded = service.get_downloaded_songs(query=query)
    total = len(all_downloaded)
    start_idx = max(0, (page - 1) * page_size)
    end_idx = start_idx + page_size
    sliced = all_downloaded[start_idx:end_idx]
    items = [format_song_item(s, service) for s in sliced]
    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

    return ApiResponse(
        success=True,
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.get("/favorites", response_model=ApiResponse[PaginatedResponse[Dict[str, Any]]])
def list_favorite_songs(
    query: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[PaginatedResponse[Dict[str, Any]]]:
    """Fetch paginated user favorite songs."""
    raw_items, total = service.get_favorites_page(query=query, page=page, page_size=page_size)
    items = [format_song_item(s, service) for s in raw_items]
    total_pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1

    return ApiResponse(
        success=True,
        data=PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        ),
    )


@router.get("/{song_id}", response_model=ApiResponse[Dict[str, Any]])
def get_song(
    song_id: int,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Get full details of a specific song, including sources and relationships."""
    details = service.get_song_details(song_id)
    if not details or not details.get("song"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Song ID {song_id} not found",
        )
    return ApiResponse(success=True, data=details)


@router.get("/{song_id}/stream")
def stream_song_audio(
    song_id: int,
    request: Request,
    service: LibraryService = Depends(get_service),
):
    """
    Stream song audio with HTTP 206 Partial Content byte range support.
    Enables seeking, scrub bar playback, and HTML5 audio element buffering.
    """
    song = service.db.get_song(song_id)
    if not song:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Song ID {song_id} not found",
        )

    file_path_str = song.file_path
    if not file_path_str:
        # Check active downloads or filesystem
        downloads = service.db.get_downloads_for_song(song_id)
        for dl in downloads:
            if dl.file_path and Path(dl.file_path).is_file():
                file_path_str = dl.file_path
                break

    if not file_path_str:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Song is not downloaded or has no physical file on disk",
        )

    file_path = Path(file_path_str)
    if not file_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Physical file missing on server: {file_path.name}",
        )

    return create_audio_stream_response(file_path, request)


@router.post("/{song_id}/rating", response_model=ApiResponse[Dict[str, Any]])
def update_rating(
    song_id: int,
    payload: SongRatingUpdate,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Update or clear user rating (1-5 or null) for a song."""
    success = service.rate_song(song_id, payload.rating)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update rating",
        )
    return ApiResponse(
        success=True,
        message="Rating updated successfully",
        data={"song_id": song_id, "rating": payload.rating},
    )


@router.post("/{song_id}/favorite", response_model=ApiResponse[Dict[str, Any]])
def toggle_favorite(
    song_id: int,
    payload: Optional[SongFavoriteUpdate] = None,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Toggle or update favorite status for a song."""
    if payload and payload.is_favorite is not None:
        current_fav = service.is_favorite(song_id)
        if current_fav != payload.is_favorite:
            service.toggle_favorite(song_id)
        is_fav = payload.is_favorite
    else:
        is_fav = service.toggle_favorite(song_id)

    return ApiResponse(
        success=True,
        message="Favorite status updated",
        data={"song_id": song_id, "is_favorite": is_fav},
    )


@router.post("/{song_id}/open-folder", response_model=ApiResponse[Dict[str, Any]])
def open_song_folder(
    song_id: int,
    request: Request,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """
    Reveal audio file in local file explorer (available only for local connections).
    """
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Folder opening is only permitted on local host connections",
        )

    song = service.db.get_song(song_id)
    if not song or not song.file_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Song is not downloaded or path is missing",
        )

    success, msg = service.open_path_in_explorer(song.file_path)
    return ApiResponse(success=success, message=msg)


@router.delete("/{song_id}", response_model=ApiResponse[Dict[str, Any]])
def delete_song(
    song_id: int,
    delete_physical_file: bool = Query(default=False),
    remove_from_library: bool = Query(default=True),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Remove song from library and optionally delete the physical audio file."""
    success = service.delete_downloaded_song(
        song_id=song_id,
        delete_from_disk=delete_physical_file,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove song",
        )
    return ApiResponse(success=True, message="Song removed successfully")
