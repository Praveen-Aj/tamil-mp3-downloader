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
    return ApiResponse(success=True, data=details)


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
