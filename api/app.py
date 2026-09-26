"""
Main FastAPI Web Application Entry Point for V6 Web Platform.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.deps import get_service
from api.routes import all_routers
from api.websocket import ws_manager
from library.service import DownloadProgressEvent

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Connects thread-safe WebSocket bridge to LibraryService progress listeners.
    """
    loop = asyncio.get_running_loop()
    ws_manager.set_loop(loop)

    service = get_service()

    def progress_listener(event: DownloadProgressEvent) -> None:
        """Listener invoked by background download workers."""
        try:
            raw_pct = getattr(event, "percent", None)
            if raw_pct is not None:
                prog_pct = round(raw_pct * 100.0 if raw_pct <= 1.0 else raw_pct, 1)
            else:
                prog_pct = round(getattr(event, "progress_percent", 0.0), 1)

            raw_speed = getattr(event, "speed_bps", None)
            if raw_speed is not None:
                spd_kbps = round(raw_speed / 1024.0, 1)
            else:
                spd_kbps = round(getattr(event, "speed_kbps", 0.0), 1)

            ws_manager.dispatch_from_thread(
                event_type="download.progress",
                data={
                    "download_id": getattr(event, "download_id", None),
                    "song_id": getattr(event, "song_id", None),
                    "track_title": getattr(event, "title", "") or getattr(event, "track_title", ""),
                    "artist": getattr(event, "artist", None),
                    "status": getattr(event, "status", "DOWNLOADING"),
                    "progress_percent": prog_pct,
                    "bytes_downloaded": getattr(event, "bytes_downloaded", 0),
                    "total_bytes": getattr(event, "total_bytes", None),
                    "speed_kbps": spd_kbps,
                    "eta_seconds": getattr(event, "eta_seconds", None),
                    "error": getattr(event, "error_message", None) or getattr(event, "error", None),
                },
            )
        except Exception:
            logger.debug("Failed dispatching progress event", exc_info=True)

    service.add_progress_listener(progress_listener)
    logger.info("FastAPI V6 application started with WebSocket progress listener.")

    yield

    service.remove_progress_listener(progress_listener)
    logger.info("FastAPI V6 application shutting down.")


def create_app() -> FastAPI:
    """FastAPI application factory."""
    app = FastAPI(
        title="Tamil MP3 Downloader API",
        description="REST and WebSocket API backend for personal Tamil music discovery, library management, and streaming.",
        version="6.0.0",
        lifespan=lifespan,
    )

    # 1. Enable CORS for local web dev and LAN devices
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. WebSocket live event endpoint
    @app.websocket("/ws/events")
    @app.websocket("/api/downloads/ws")
    @app.websocket("/ws/downloads")
    async def websocket_events(websocket: WebSocket) -> None:
        await ws_manager.connect(websocket)
        try:
            while True:
                # Keepalive / ping reception
                data = await websocket.receive_text()
                if data == "ping":
                    await websocket.send_text('{"event":"pong"}')
        except WebSocketDisconnect:
            ws_manager.disconnect(websocket)
        except Exception:
            ws_manager.disconnect(websocket)

    # 3. Mount all API route modules
    for router in all_routers:
        app.include_router(router, prefix="/api")

    # 4. Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.error("Unhandled error processing %s: %s", request.url.path, str(exc), exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": "Internal server error occurred",
                "message": str(exc),
            },
        )

    # 5. Serve frontend static assets if compiled in web/dist
    from pathlib import Path
    dist_dir = Path(__file__).resolve().parent.parent / "web" / "dist"
    if dist_dir.is_dir() and (dist_dir / "index.html").is_file():
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse
        from fastapi import HTTPException

        assets_dir = dist_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        @app.get("/")
        async def serve_index() -> FileResponse:
            return FileResponse(dist_dir / "index.html")

        @app.get("/{full_path:path}")
        async def serve_spa_fallback(full_path: str) -> FileResponse:
            """Catch-all route handler supporting HTML5 history client-side routing."""
            if full_path.startswith("api/") or full_path == "api" or full_path.startswith("ws/") or full_path == "ws":
                raise HTTPException(status_code=404, detail="Not Found")
            file_candidate = dist_dir / full_path
            if full_path and file_candidate.is_file():
                return FileResponse(file_candidate)
            return FileResponse(dist_dir / "index.html")

    return app


# Default ASGI app instance
app = create_app()
