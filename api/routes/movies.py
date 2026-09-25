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


from library.canonical import clean_song_title


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
    movie_dict = {}
    if movie_obj and hasattr(movie_obj, "title"):
        movie_dict = {
            "id": movie_obj.id,
            "name": movie_obj.title,
            "title": movie_obj.title,
            "year": movie_obj.year,
            "director": movie_obj.director,
            "poster_url": movie_obj.poster_url,
            "banner_url": getattr(movie_obj, "banner_url", None),
            "local_poster_path": getattr(movie_obj, "local_poster_path", None),
        }
    elif isinstance(movie_obj, dict):
        movie_dict = dict(movie_obj)
        if "name" not in movie_dict:
            movie_dict["name"] = movie_dict.get("title", "")

    # Clean titles in songs list
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

    stats = details.get("stats") or service.db.get_movie_download_stats(movie_id)
    if isinstance(movie_dict, dict):
        movie_dict["total_songs"] = stats.get("total", len(clean_songs))
        movie_dict["downloaded_count"] = stats.get("downloaded", 0)
        movie_dict["missing_count"] = stats.get("missing", 0)

    return ApiResponse(
        success=True,
        data={
            "movie": movie_dict,
            "songs": clean_songs,
            "stats": stats,
            "cast": details.get("cast", []),
            "composers": details.get("composers", []),
        },
    )


@router.get("/{movie_id}/songs", response_model=ApiResponse[Dict[str, Any]])
def get_movie_songs(
    movie_id: int,
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """Get songs and details for a specific movie."""
    return get_movie(movie_id, service)


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
