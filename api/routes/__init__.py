"""
API Routes Package.
"""

from api.routes.system import router as system_router
from api.routes.songs import router as songs_router
from api.routes.movies import router as movies_router
from api.routes.artists import router as artists_router
from api.routes.charts import router as charts_router
from api.routes.playlists import router as playlists_router
from api.routes.search import router as search_router
from api.routes.downloads import router as downloads_router
from api.routes.imports import router as imports_router
from api.routes.artwork import router as artwork_router
from api.routes.settings import router as settings_router

all_routers = [
    system_router,
    songs_router,
    movies_router,
    artists_router,
    charts_router,
    playlists_router,
    search_router,
    downloads_router,
    imports_router,
    artwork_router,
    settings_router,
]

__all__ = ["all_routers"]
