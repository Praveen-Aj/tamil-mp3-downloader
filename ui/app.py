"""
Tamil MP3 Downloader — Modular UI Application (Phase 1).

Main application entry window mounting SidebarNav, dynamic View container, and StatusBar.
Encapsulates all UI views:
- Dashboard (Phase 2)
- Library (Phase 3)
- Discover (Phase 5)
- Discovery Results (Phase 6)
- Downloads (Phase 8)
- Import (Phase 9)
- Sources (Phase 10)
- Settings (Phase 11)
"""

import logging
from pathlib import Path
from typing import Dict, Any, Optional

import customtkinter as ctk

from ui.components.sidebar import SidebarNav
from ui.components.status_bar import StatusBar
from ui.services.library_service import LibraryService
from ui.views.dashboard import DashboardView
from ui.views.discover import DiscoverView
from ui.views.discovery_results import DiscoveryResultsView
from ui.views.downloads import DownloadsView
from ui.views.import_view import ImportView
from ui.views.library import LibraryView
from ui.views.sources import SourcesView
from ui.views.settings_view import SettingsView

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class TamilMP3App(ctk.CTk):
    """
    Main Modular GUI Window.
    """

    def __init__(self, db_path: Optional[Path] = None) -> None:
        super().__init__()

        self.title("🎵 Tamil MP3 Downloader — Canonical Library Architecture")
        self.geometry("1400x900")
        self.minsize(1100, 720)

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
        self.service = LibraryService(db_path=db_path)

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # ── 1. Sidebar Navigation ───────────────────────────────────
        self.sidebar = SidebarNav(self, on_view_change=self.show_view)
        self.sidebar.grid(row=0, column=0, sticky="nsew")

        # ── 2. Active View Container ─────────────────────────────────
        self.view_container = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.view_container.grid(row=0, column=1, sticky="nsew")
        self.view_container.grid_rowconfigure(0, weight=1)
        self.view_container.grid_columnconfigure(0, weight=1)

        # Views Cache
        self.views: Dict[str, ctk.CTkFrame] = {}
        self.current_view_name: Optional[str] = None

        self._init_views()

        # ── 3. Bottom Status Bar ─────────────────────────────────────
        self.status_bar = StatusBar(self)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")

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

        self.views["library"] = LibraryView(
            self.view_container,
            service=self.service,
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

    def show_view(self, view_name: str) -> None:
        """Switch active view frame."""
        if view_name not in self.views:
            logger.warning(f"Unknown view name requested: {view_name}")
            return

        if self.current_view_name and self.current_view_name in self.views:
            self.views[self.current_view_name].grid_forget()

        self.current_view_name = view_name
        target_view = self.views[view_name]
        target_view.grid(row=0, column=0, sticky="nsew")

        # Refresh view if method present
        if hasattr(target_view, "refresh"):
            target_view.refresh()

        self.refresh_status_bar()

    def refresh_status_bar(self) -> None:
        """Update global status bar metrics."""
        stats = self.service.get_dashboard_stats()
        self.status_bar.update_stats(
            total=stats.get("total_songs", 0),
            owned=stats.get("owned_songs", 0),
            healthy_sources=stats.get("healthy_sources", "3/3"),
            active_dl=stats.get("active_downloads", 0),
        )

    def _on_discovery_complete(self, results: Dict[str, Any]) -> None:
        """Callback when discovery finishes — switch to Results View."""
        self.show_view("results")

    def _on_downloads_started(self, dl_ids: list) -> None:
        """Callback when downloads start — switch to Downloads Queue View."""
        self.show_view("downloads")


def main() -> None:
    app = TamilMP3App()
    app.mainloop()


if __name__ == "__main__":
    main()
