"""
Global Search Router for V6 Web API.
"""

from typing import Any, Dict, List
from fastapi import APIRouter, Depends, Query

from api.deps import get_service
from api.schemas.common import ApiResponse
from library.service import LibraryService

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("/global", response_model=ApiResponse[Dict[str, Any]])
def global_search(
    q: str = Query(default="", min_length=1),
    limit: int = Query(default=10, ge=1, le=50),
    service: LibraryService = Depends(get_service),
) -> ApiResponse[Dict[str, Any]]:
    """
    Unified global search querying songs, movies, artists, playlists, and charts.
    """
    clean_query = q.strip()
    if not clean_query:
        return ApiResponse(
            success=True,
            data={
                "songs": [],
                "movies": [],
                "artists": [],
                "playlists": [],
                "charts": [],
            },
        )

    # 1. Search Songs
    songs = service.db.search_songs(clean_query, limit=limit)
    song_results = [
        {
            "id": s.id,
            "title": s.title,
            "artist": s.artist,
            "album": s.album,
            "year": s.year,
            "state": s.state.value if hasattr(s.state, "value") else str(s.state),
            "is_downloaded": bool(s.file_path),
        }
        for s in songs
    ]

    # 2. Search Movies
    raw_movies, _ = service.get_movies_page(query=clean_query, page=1, page_size=limit)
    movies_data = [
        {
            **m,
            "name": m.get("title") or m.get("name", ""),
            "title": m.get("title") or m.get("name", ""),
        }
        for m in raw_movies
    ]

    # 3. Search Artists
    artists_data, _ = service.get_artists_page(query=clean_query, page=1, page_size=limit)

    # 4. Search Playlists
    playlists_data, _ = service.get_playlists_page(query=clean_query, page=1, page_size=limit)

    # 5. Search Charts
    all_charts = service.db.list_charts()
    chart_results = [
        {
            "id": c.id,
            "name": getattr(c, "title", getattr(c, "name", "")),
            "frequency": getattr(c, "frequency", "weekly"),
            "total_entries": getattr(c, "total_entries", 0),
        }
        for c in all_charts
        if clean_query.lower() in getattr(c, "title", "").lower()
        or (getattr(c, "chart_type", None) and clean_query.lower() in c.chart_type.lower())
    ][:limit]


    return ApiResponse(
        success=True,
        data={
            "query": clean_query,
            "songs": song_results,
            "movies": movies_data,
            "artists": artists_data,
            "playlists": playlists_data,
            "charts": chart_results,
        },
    )
