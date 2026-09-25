"""
Artists Router for V6 Web API.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_service
from api.schemas.common import ApiResponse, PaginatedResponse
from api.schemas.download import DownloadPlanResponse, format_download_plan
from library.service import LibraryService

router = APIRouter(prefix="/artists", tags=["Artists"])


@router.get("", response_model=ApiResponse[PaginatedResponse[Dict[str, Any]]])
def list_artists(
    query: str = Query(default=""),
    role: Optional[str] = Query(default=None),
    sort_by: str = Query(default="name"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[PaginatedResponse[Dict[str, Any]]]:
    """Fetch paginated artists/singers/composers with role filtering and statistics."""
    actual_role = role if role and role.lower() != "all" else None
    items, total = service.get_artists_page(
        query=query,
        role=actual_role,
        sort_by=sort_by,
        ascending=(sort_order.lower() == "asc"),
        page=page,
        page_size=page_size,
    )
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


from library.canonical import clean_song_title


@router.get("/{artist_id}", response_model=ApiResponse[Dict[str, Any]])
def get_artist(
    artist_id: int,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Get full details of a specific artist, including discography and filmography."""
    details = service.get_artist_details(artist_id)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Artist ID {artist_id} not found",
        )

    # Clean song titles
    raw_songs = details.get("songs", [])
    clean_songs = []
    for s in raw_songs:
        if isinstance(s, dict):
            s_dict = dict(s)
            s_dict["title"] = clean_song_title(s_dict.get("title", ""))
            clean_songs.append(s_dict)
        elif hasattr(s, "title"):
            clean_songs.append({
                "id": s.id,
                "title": clean_song_title(s.title),
                "artist": getattr(s, "artist", "") or "",
                "album": getattr(s, "album", "") or "",
                "year": getattr(s, "year", None),
                "state": s.state.value if hasattr(s.state, "value") else str(s.state),
                "quality": getattr(s, "quality_kbps", None),
                "file_path": getattr(s, "file_path", None),
            })
        else:
            clean_songs.append(s)

    details["songs"] = clean_songs
    stats = details.get("stats", {})
    artist_obj = details.get("artist")
    if artist_obj and hasattr(artist_obj, "name"):
        details["artist"] = {
            "id": artist_obj.id,
            "name": artist_obj.name,
            "role": artist_obj.role,
            "photo_url": artist_obj.photo_url,
            "local_photo_path": artist_obj.local_photo_path,
            "bio": artist_obj.bio,
            "total_songs": stats.get("total", len(clean_songs)),
            "total_tracks": stats.get("total", len(clean_songs)),
            "downloaded_songs": stats.get("downloaded", 0),
            "downloaded_tracks": stats.get("downloaded", 0),
            "total_movies": stats.get("movies_count", 0),
            "total_soundtracks": stats.get("movies_count", 0),
        }
    elif isinstance(artist_obj, dict):
        artist_dict = dict(artist_obj)
        artist_dict["total_songs"] = stats.get("total", len(clean_songs))
        artist_dict["total_tracks"] = stats.get("total", len(clean_songs))
        artist_dict["downloaded_songs"] = stats.get("downloaded", 0)
        artist_dict["downloaded_tracks"] = stats.get("downloaded", 0)
        details["artist"] = artist_dict

    return ApiResponse(success=True, data=details)


@router.get("/{artist_id}/songs", response_model=ApiResponse[Dict[str, Any]])
def get_artist_songs(
    artist_id: int,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Get tracks and detailed information for a specific artist."""
    return get_artist(artist_id, service)


@router.post("/{artist_id}/plan", response_model=ApiResponse[DownloadPlanResponse])
def plan_artist_download(
    artist_id: int,
    mode: str = Query(default="missing", pattern="^(all|missing)$"),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[DownloadPlanResponse]:
    """Generate download plan for all or missing songs by an artist."""
    if mode == "all":
        plan = service.plan_artist_download_all(artist_id)
    else:
        plan = service.plan_artist_download_missing(artist_id)

    return ApiResponse(
        success=True,
        data=format_download_plan(plan),
    )


@router.post("/{artist_id}/download", response_model=ApiResponse[Dict[str, Any]])
def execute_artist_download(
    artist_id: int,
    mode: str = Query(default="missing", pattern="^(all|missing)$"),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Execute background downloads for all or missing songs by an artist."""
    if mode == "all":
        plan = service.plan_artist_download_all(artist_id)
    else:
        plan = service.plan_artist_download_missing(artist_id)

    queued_count = service.execute_download_plan(plan)
    return ApiResponse(
        success=True,
        message=f"Queued {queued_count} downloads for artist",
        data={"artist_id": artist_id, "queued_count": queued_count},
    )
