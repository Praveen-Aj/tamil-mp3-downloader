"""
Movies Router for V6 Web API.
"""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_service
from api.schemas.common import ApiResponse, PaginatedResponse
from api.schemas.download import DownloadPlanResponse, format_download_plan
from library.service import LibraryService

router = APIRouter(prefix="/movies", tags=["Movies"])


@router.get("", response_model=ApiResponse[PaginatedResponse[Dict[str, Any]]])
def list_movies(
    query: str = Query(default=""),
    sort_by: str = Query(default="name"),
    sort_order: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[PaginatedResponse[Dict[str, Any]]]:
    """Fetch paginated movies with search and song/download statistics."""
    sort_col = "title" if sort_by in ("name", "title") else sort_by
    items, total = service.get_movies_page(
        query=query,
        sort_by=sort_col,
        ascending=(sort_order.lower() == "asc"),
        page=page,
        page_size=page_size,
    )

    for it in items:
        if "name" not in it:
            it["name"] = it.get("title", "")

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


@router.get("/{movie_id}", response_model=ApiResponse[Dict[str, Any]])
def get_movie(
    movie_id: int,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Get full details of a specific movie, including cast, composers, and tracklist."""
    details = service.get_movie_details(movie_id)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Movie ID {movie_id} not found",
        )

    movie_obj = details.get("movie")
    if movie_obj and hasattr(movie_obj, "title"):
        details["movie"] = {
            "id": movie_obj.id,
            "name": movie_obj.title,
            "title": movie_obj.title,
            "year": movie_obj.year,
            "director": movie_obj.director,
            "poster_url": movie_obj.poster_url,
        }
    elif isinstance(movie_obj, dict) and "name" not in movie_obj:
        movie_obj["name"] = movie_obj.get("title", "")

    return ApiResponse(success=True, data=details)


@router.post("/{movie_id}/plan", response_model=ApiResponse[DownloadPlanResponse])
def plan_movie_download(
    movie_id: int,
    mode: str = Query(default="missing", pattern="^(all|missing)$"),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[DownloadPlanResponse]:
    """Generate download plan for all or missing songs in a movie."""
    if mode == "all":
        plan = service.plan_movie_download_all(movie_id)
    else:
        plan = service.plan_movie_download_missing(movie_id)

    return ApiResponse(
        success=True,
        data=format_download_plan(plan),
    )


@router.post("/{movie_id}/download", response_model=ApiResponse[Dict[str, Any]])
def execute_movie_download(
    movie_id: int,
    mode: str = Query(default="missing", pattern="^(all|missing)$"),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Execute background downloads for all or missing songs in a movie."""
    if mode == "all":
        plan = service.plan_movie_download_all(movie_id)
    else:
        plan = service.plan_movie_download_missing(movie_id)

    queued_count = service.execute_download_plan(plan)
    return ApiResponse(
        success=True,
        message=f"Queued {queued_count} downloads for movie",
        data={"movie_id": movie_id, "queued_count": queued_count},
    )
