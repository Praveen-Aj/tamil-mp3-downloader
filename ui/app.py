"""
Tamil MP3 Downloader — Modular UI Application.

Main application entry window mounting SidebarNav, dynamic View container, and StatusBar.
Encapsulates all UI views:
- Dashboard
- Add Music (Universal URL & Playlist Import)
- Library (Canonical SQLite Library)
- Discover (Regional Discovery)
- Review Results (Conflict & Match Review)
- Downloads (Downloads Manager Queue)
- Sources (Source Health Dashboard)
- Settings (Settings Center)
- Help (Help & User Guide)
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

import customtkinter as ctk

from ui import theme
from ui.components.sidebar import SidebarNav
from ui.components.status_bar import StatusBar
from ui.services.library_service import LibraryService
from ui.views.add_music import AddMusicView
from ui.views.dashboard import DashboardView
from ui.views.discover import DiscoverView
from ui.views.discovery_results import DiscoveryResultsView
from ui.views.downloads import DownloadsView
from ui.views.downloaded_songs import DownloadedSongsView
from ui.views.help_view import HelpView
from ui.views.import_view import ImportView
from ui.views.library import LibraryView
from ui.views.movies_view import MoviesView
from ui.views.movie_detail_view import MovieDetailView
from ui.views.artists_view import ArtistsView
from ui.views.artist_detail_view import ArtistDetailView
from ui.views.charts_view import ChartsView
from ui.views.chart_detail_view import ChartDetailView
from ui.views.playlists_view import PlaylistsView
from ui.views.playlist_detail_view import PlaylistDetailView
from ui.views.sources import SourcesView
from ui.views.settings_view import SettingsView


logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class TamilMP3App(ctk.CTk):
    """
    Main Modular GUI Window.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        service: Optional[LibraryService] = None,
    ) -> None:
        super().__init__()

        self.title("🎵 Tamil MP3 Downloader — Desktop Music Downloader & Library Manager")
        self.geometry("1400x900")
        self.minsize(1000, 600)

        # Taskbar icon support
        try:
            from ctypes import windll
            icon_path = Path(__file__).parent.parent / "Icons" / "Tamil_mp3_downloader.ico"
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
                try:
                    windll.shell32.SetCurrentProcessExplicitAppUserModelID("TamilMP3Downloader.App")
                except Exception:
                    pass
        except Exception:
            pass

        # ── Initialize Central Service ──────────────────────────────
        self.service = service or LibraryService(db_path=db_path)

        self.configure(fg_color=theme.BG_APP)
        try:
            self.config(bg=theme.BG_APP)
        except Exception:
            pass
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(1, weight=1)

        # ── 1. Sidebar Navigation ───────────────────────────────────
        self.sidebar = SidebarNav(self, on_view_change=self.show_view)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # ── 2. Active View Container ─────────────────────────────────
        self.view_container = ctk.CTkFrame(self, corner_radius=0, fg_color=theme.BG_APP)
        self.view_container.grid(row=0, column=1, sticky="nsew")
        self.view_container.grid_rowconfigure(0, weight=1)
        self.view_container.grid_columnconfigure(0, weight=1)

        # Views Cache
        self.views: Dict[str, ctk.CTkFrame] = {}
        self.current_view_name: Optional[str] = None

        self._init_views()

        # ── 3. Bottom Status Bar ─────────────────────────────────────
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="nsew")

        # Initial view
        self.show_view("dashboard")
        self.refresh_status_bar()

    def _init_views(self) -> None:
        """Instantiate views."""
        self.views["dashboard"] = DashboardView(
            self.view_container,
            service=self.service,
            on_navigate=self.show_view,
        )

        self.views["add_music"] = AddMusicView(
            self.view_container,
            service=self.service,
            on_navigate_downloads=lambda: self.show_view("downloads"),
        )

        self.views["library"] = LibraryView(
            self.view_container,
            service=self.service,
            on_start_downloads=self._on_downloads_started,
        )

        self.views["movies"] = MoviesView(
            self.view_container,
            service=self.service,
            on_open_movie=self._open_movie_detail,
            on_navigate=self.show_view,
        )

        self.views["movie_detail"] = MovieDetailView(
            self.view_container,
            service=self.service,
            on_back=lambda: self.show_view("movies"),
            on_start_downloads=self._on_downloads_started,
            on_open_artist=self._open_artist_detail,
        )

        self.views["artists"] = ArtistsView(
            self.view_container,
            service=self.service,
            on_open_artist=self._open_artist_detail,
            on_navigate=self.show_view,
        )

        self.views["artist_detail"] = ArtistDetailView(
            self.view_container,
            service=self.service,
            on_back=lambda: self.show_view("artists"),
            on_open_movie=self._open_movie_detail,
            on_start_downloads=self._on_downloads_started,
        )

        self.views["charts"] = ChartsView(
            self.view_container,
            service=self.service,
            on_open_chart=self._open_chart_detail,
            on_navigate=self.show_view,
        )

        self.views["chart_detail"] = ChartDetailView(
            self.view_container,
            service=self.service,
            on_back=lambda: self.show_view("charts"),
            on_open_artist=self._open_artist_detail,
            on_open_movie=self._open_movie_detail,
            on_start_downloads=self._on_downloads_started,
        )

        self.views["playlists"] = PlaylistsView(
            self.view_container,
            service=self.service,
            on_open_playlist=self._open_playlist_detail,
            on_navigate=self.show_view,
            on_open_artist=self._open_artist_detail,
            on_open_movie=self._open_movie_detail,
        )

        self.views["playlist_detail"] = PlaylistDetailView(
            self.view_container,
            service=self.service,
            on_back=lambda: self.show_view("playlists"),
            on_open_artist=self._open_artist_detail,
            on_open_movie=self._open_movie_detail,
            on_start_downloads=self._on_downloads_started,
        )

        self.views["discover"] = DiscoverView(
            self.view_container,
            service=self.service,
            on_discovery_complete=self._on_discovery_complete,
        )

        self.views["results"] = DiscoveryResultsView(
            self.view_container,
            service=self.service,
            on_start_downloads=self._on_downloads_started,
        )

        self.views["downloads"] = DownloadsView(
            self.view_container,
            service=self.service,
            on_navigate_add_music=lambda: self.show_view("add_music"),
        )

        self.views["downloaded_songs"] = DownloadedSongsView(
            self.view_container,
            service=self.service,
            on_navigate_add_music=lambda: self.show_view("add_music"),
        )


        self.views["import"] = ImportView(
            self.view_container,
            service=self.service,
        )

        self.views["sources"] = SourcesView(
            self.view_container,
            service=self.service,
        )

        self.views["settings"] = SettingsView(
            self.view_container,
            service=self.service,
        )

        self.views["help"] = HelpView(
            self.view_container,
        )

    def _open_movie_detail(self, movie_id: int) -> None:
        """Open detailed movie inspection view."""
        if "movie_detail" in self.views:
            detail_view = self.views["movie_detail"]
            if hasattr(detail_view, "set_movie"):
                detail_view.set_movie(movie_id)
            self.show_view("movie_detail")

    def _open_artist_detail(self, artist_id: int) -> None:
        """Open detailed artist/person inspection view."""
        if "artist_detail" in self.views:
            detail_view = self.views["artist_detail"]
            if hasattr(detail_view, "set_artist"):
                detail_view.set_artist(artist_id)
            self.show_view("artist_detail")

    def _open_chart_detail(self, chart_id: str) -> None:
        """Open detailed curated chart inspection view."""
        if "chart_detail" in self.views:
            detail_view = self.views["chart_detail"]
            if hasattr(detail_view, "load_chart"):
                detail_view.load_chart(chart_id)
            self.show_view("chart_detail")

    def _open_playlist_detail(self, playlist_id: int) -> None:
        """Open detailed user playlist view."""
        if "playlist_detail" in self.views:
            detail_view = self.views["playlist_detail"]
            if hasattr(detail_view, "load_playlist"):
                detail_view.load_playlist(playlist_id)
            self.show_view("playlist_detail")

    def show_view(self, view_name: str) -> None:
        """Switch active view frame."""
        if view_name not in self.views:
            logger.warning(f"Unknown view name requested: {view_name}")
            return

        for name, v in self.views.items():
            if name == view_name:
                v.grid(row=0, column=0, sticky="nsew")
                v.tkraise()
            else:
                v.grid_remove()

        self.current_view_name = view_name
        if view_name == "movie_detail":
            sidebar_key = "movies"
        elif view_name == "artist_detail":
            sidebar_key = "artists"
        elif view_name == "chart_detail":
            sidebar_key = "charts"
        elif view_name == "playlist_detail":
            sidebar_key = "playlists"
        else:
            sidebar_key = view_name
        self.sidebar.set_active(sidebar_key)
        target_view = self.views[view_name]

        # Refresh view if method present
        if hasattr(target_view, "refresh"):
            target_view.refresh()

        self.refresh_status_bar()

    def navigate_to(self, view_name: str) -> None:
        """Alias for show_view."""
        self.show_view(view_name)

    def refresh_status_bar(self) -> None:
        """Update global status bar metrics and sidebar badge counters."""
        stats = self.service.get_dashboard_stats()
        active_dl = stats.get("active_downloads", 0)
        unowned_cnt = stats.get("ready_downloads", 0)

        self.status_bar.update_stats(
            total=stats.get("total_songs", 0),
            owned=stats.get("owned_songs", 0),
            healthy_sources=stats.get("healthy_sources", "3/3"),
            active_dl=active_dl,
        )

        # Update sidebar notification badge pills
        self.sidebar.update_badge("downloads", active_dl)

    def _on_discovery_complete(self, results: Dict[str, Any]) -> None:
        """Callback when discovery finishes — switch to Music Library View with toast notification."""
        registered = results.get("unique_registered", 0)
        self.show_view("library")
        self.status_bar.set_message(f"🎉 Discovery Complete: {registered} songs added to library")

    def _on_downloads_started(self, dl_ids: list) -> None:
        """Callback when downloads start — switch to Downloads Queue View."""
        self.show_view("downloads")


def main() -> None:
    app = TamilMP3App()
    app.mainloop()


if __name__ == "__main__":
    main()
