"""
Playlists Router for V6 Web API.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_service
from api.schemas.common import ApiResponse, PaginatedResponse
from api.schemas.playlist import PlaylistCreate, PlaylistUpdate, PlaylistItemAdd, PlaylistItemMove
from api.schemas.download import DownloadPlanResponse, format_download_plan
from library.service import LibraryService

router = APIRouter(prefix="/playlists", tags=["Playlists"])


@router.get("", response_model=ApiResponse[PaginatedResponse[Dict[str, Any]]])
def list_playlists(
    query: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[PaginatedResponse[Dict[str, Any]]]:
    """Fetch paginated playlists with song counts and download metrics."""
    items, total = service.get_playlists_page(query=query, page=page, page_size=page_size)
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


@router.post("", response_model=ApiResponse[Dict[str, Any]])
def create_playlist(
    payload: PlaylistCreate,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Create a new personal music playlist."""
    playlist_id = service.create_playlist(payload.name, payload.description or "")
    if not playlist_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to create playlist",
        )
    return ApiResponse(
        success=True,
        message="Playlist created successfully",
        data={"id": playlist_id, "name": payload.name},
    )


@router.get("/{playlist_id}", response_model=ApiResponse[Dict[str, Any]])
def get_playlist(
    playlist_id: int,
    query: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Get full details of a playlist including tracklist and download stats."""
    details = service.get_playlist_details(
        playlist_id=playlist_id,
        query=query,
        page=page,
        page_size=page_size,
    )
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Playlist ID {playlist_id} not found",
        )

    playlist_obj = details["playlist"]
    data = {
        "id": playlist_obj.id,
        "name": playlist_obj.name,
        "description": playlist_obj.description,
        "stats": details["stats"],
        "items": details["items"],
        "total_matching": details["total_matching"],
    }
    return ApiResponse(success=True, data=data)


@router.delete("/{playlist_id}", response_model=ApiResponse[Dict[str, Any]])
def delete_playlist(
    playlist_id: int,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Delete a playlist without deleting underlying canonical songs."""
    success = service.delete_playlist(playlist_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to delete playlist",
        )
    return ApiResponse(success=True, message="Playlist deleted successfully")


@router.post("/{playlist_id}/items", response_model=ApiResponse[Dict[str, Any]])
def add_song_to_playlist(
    playlist_id: int,
    payload: PlaylistItemAdd,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Append a canonical song to the playlist."""
    added = service.add_songs_to_playlist(playlist_id, [payload.song_id])
    if added == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Song already in playlist or invalid song ID",
        )
    return ApiResponse(success=True, message="Song added to playlist")


@router.delete("/{playlist_id}/items/{song_id}", response_model=ApiResponse[Dict[str, Any]])
def remove_song_from_playlist(
    playlist_id: int,
    song_id: int,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Remove a song from the playlist."""
    success = service.remove_song_from_playlist(playlist_id, song_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to remove song from playlist",
        )
    return ApiResponse(success=True, message="Song removed from playlist")


@router.post("/{playlist_id}/items/{song_id}/move", response_model=ApiResponse[Dict[str, Any]])
def move_playlist_item(
    playlist_id: int,
    song_id: int,
    payload: PlaylistItemMove,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Reorder a playlist item up or down."""
    success = service.move_playlist_song(playlist_id, song_id, payload.direction)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to move playlist item",
        )
    return ApiResponse(success=True, message=f"Item moved {payload.direction}")


@router.post("/{playlist_id}/plan", response_model=ApiResponse[DownloadPlanResponse])
def plan_playlist_download(
    playlist_id: int,
    mode: str = Query(default="missing", pattern="^(all|missing)$"),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[DownloadPlanResponse]:
    """Generate download plan for all or missing songs in a playlist."""
    if mode == "all":
        plan = service.plan_playlist_download_all(playlist_id)
    else:
        plan = service.plan_playlist_download_missing(playlist_id)

    return ApiResponse(
        success=True,
        data=format_download_plan(plan),
    )


@router.post("/{playlist_id}/download", response_model=ApiResponse[Dict[str, Any]])
def execute_playlist_download(
    playlist_id: int,
    mode: str = Query(default="missing", pattern="^(all|missing)$"),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Execute background downloads for all or missing songs in a playlist."""
    if mode == "all":
        plan = service.plan_playlist_download_all(playlist_id)
    else:
        plan = service.plan_playlist_download_missing(playlist_id)

    queued_count = service.execute_download_plan(plan)
    return ApiResponse(
        success=True,
        message=f"Queued {queued_count} downloads for playlist",
        data={"playlist_id": playlist_id, "queued_count": queued_count},
    )
