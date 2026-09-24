"""
Artwork Delivery and Fallback Generator Router for V6 Web API.
"""

import io
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from api.deps import get_artwork_manager, get_service
from library.artwork import ArtworkManager
from library.service import LibraryService

router = APIRouter(prefix="/artwork", tags=["Artwork"])


@router.get("/{category}/{entity_id}")
def get_artwork(
    category: str,
    entity_id: str,
    width: int = Query(default=300, ge=32, le=1024),
    height: int = Query(default=300, ge=32, le=1024),
    service: LibraryService = Depends(get_service),
    artwork_mgr: ArtworkManager = Depends(get_artwork_manager),
) -> Response:
    """
    Serve high-resolution artwork or procedural aesthetic fallback for any library entity.
    Categories: song, movie, artist, chart, playlist.
    """
    valid_categories = {"song", "movie", "artist", "chart", "playlist"}
    if category.lower() not in valid_categories:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid category: {category}. Valid: {valid_categories}",
        )

    cat = category.lower()
    title = f"{cat.capitalize()} #{entity_id}"
    subtitle: Optional[str] = None
    remote_key: Optional[str] = None
    local_path: Optional[str] = None

    if cat == "movie":
        try:
            movie = service.db.get_movie(int(entity_id))
            if movie:
                title = getattr(movie, "title", getattr(movie, "name", "Movie"))
                subtitle = str(movie.year) if movie.year else None
                remote_key = movie.poster_url
        except (ValueError, TypeError):
            pass

    elif cat == "artist":
        try:
            artist = service.db.get_artist(int(entity_id))
            if artist:
                title = artist.name
                remote_key = getattr(artist, "photo_url", getattr(artist, "image_url", None))
        except (ValueError, TypeError):
            pass

    elif cat == "chart":
        chart = service.db.get_chart(str(entity_id))
        if chart:
            title = getattr(chart, "title", getattr(chart, "name", "Chart"))
            subtitle = getattr(chart, "frequency", "CHART").upper()
            remote_key = getattr(chart, "source_url", None)

    elif cat == "playlist":
        try:
            playlist = service.db.get_playlist(int(entity_id))
            if playlist:
                title = playlist.name
                subtitle = "Playlist"
        except (ValueError, TypeError):
            pass

    elif cat == "song":
        try:
            song = service.db.get_song(int(entity_id))
            if song:
                title = song.title
                subtitle = song.artist
                local_path = song.file_path
        except (ValueError, TypeError):
            pass

    # Use ArtworkManager to resolve image (local embedded > cached disk > remote > generated fallback)
    pil_image = artwork_mgr.get_artwork(
        source=remote_key or local_path,
        size=(width, height),
        entity_type=cat,
        fallback_text=title,
    )

    buf = io.BytesIO()
    if pil_image.mode in ("RGBA", "P", "LA"):
        pil_image = pil_image.convert("RGB")
    pil_image.save(buf, format="JPEG", quality=85)
    image_bytes = buf.getvalue()

    return Response(
        content=image_bytes,
        media_type="image/jpeg",
        headers={
            "Cache-Control": "public, max-age=86400, immutable",
            "Content-Length": str(len(image_bytes)),
        },
    )
