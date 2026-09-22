"""
Sidebar Navigation Component for CustomTkinter.

Provides categorized navigation (LIBRARY, DOWNLOADS, SYSTEM),
active-state visual indicators, and live badge counters.
"""

from typing import Callable, Dict, Optional
import customtkinter as ctk

from ui import theme


class SidebarNav(ctk.CTkFrame):
    """
    Polished sidebar navigation panel with categorized groupings
    and real-time notification badge pills.
    """

    def __init__(
        self,
        master: ctk.CTk,
        on_view_change: Callable[[str], None],
        **kwargs
    ):
        super().__init__(
            master,
            width=230,
            corner_radius=0,
            fg_color=theme.BG_SIDEBAR,
            **kwargs
        )
        self.on_view_change = on_view_change
        self._buttons: Dict[str, ctk.CTkButton] = {}
        self._badges: Dict[str, ctk.CTkLabel] = {}
        self._active_key: str = "dashboard"

        self.grid_propagate(False)

        # ── 1. App Brand Header ─────────────────────────────────────
        brand_frame = ctk.CTkFrame(self, fg_color="transparent")
        brand_frame.pack(fill="x", padx=18, pady=(22, 18))

        logo_icon = ctk.CTkLabel(
            brand_frame,
            text="🎵",
            font=ctk.CTkFont(size=24),
        )
        logo_icon.pack(side="left", padx=(0, 10))

        title_box = ctk.CTkFrame(brand_frame, fg_color="transparent")
        title_box.pack(side="left", fill="both")

        app_title = ctk.CTkLabel(
            title_box,
            text="TAMIL MP3",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        )
        app_title.pack(anchor="w")

        app_sub = ctk.CTkLabel(
            title_box,
            text="Music Manager",
            font=theme.font_caption(),
            text_color=theme.PRIMARY_LIGHT,
            anchor="w",
        )
        app_sub.pack(anchor="w")

        # Subtle separator
        sep = ctk.CTkFrame(self, height=1, fg_color=theme.BORDER)
        sep.pack(fill="x", padx=16, pady=(0, 12))

        # ── 2. Categorized Navigation Groups ────────────────────────
        # Group: DOWNLOADS
        self._create_group_label("DOWNLOADS")
        self._create_nav_button("add_music", "⚡  Add Music", view_key="add_music", is_accent=True)
        self._create_nav_button("downloads", "📥  Downloads", view_key="downloads", badge_key="downloads")
        self._create_nav_button("downloaded_songs", "🎵  Downloaded Songs", view_key="downloaded_songs")

        # Group: LIBRARY
        self._create_group_label("LIBRARY")
        self._create_nav_button("dashboard", "📊  Dashboard", view_key="dashboard")
        self._create_nav_button("library", "📚  Music Library", view_key="library")
        self._create_nav_button("movies", "🎬  Movies", view_key="movies")
        self._create_nav_button("artists", "👥  Artists & People", view_key="artists")
        self._create_nav_button("charts", "🔥  Charts & Top 100", view_key="charts")
        self._create_nav_button("playlists", "📑  Playlists & Favorites", view_key="playlists")
        self._create_nav_button("discover", "🔍  Discover Regional", view_key="discover")

        # Group: SYSTEM
        self._create_group_label("SYSTEM")
        self._create_nav_button("settings", "⚙️  Settings", view_key="settings")
        self._create_nav_button("help", "❓  Help & Guide", view_key="help")

        # Highlight default
        self.set_active("dashboard")


    def _create_group_label(self, title: str) -> None:
        """Section header label."""
        lbl = ctk.CTkLabel(
            self,
            text=title,
            font=theme.font_badge(),
            text_color=theme.TEXT_DIM,
            anchor="w",
        )
        lbl.pack(fill="x", padx=20, pady=(10, 4))

    def _create_nav_button(
        self,
        key: str,
        label: str,
        view_key: str,
        is_accent: bool = False,
        badge_key: Optional[str] = None,
    ) -> None:
        """Create styled navigation button with badge container."""
        btn_container = ctk.CTkFrame(self, fg_color="transparent")
        btn_container.pack(fill="x", padx=12, pady=2)

        btn = ctk.CTkButton(
            btn_container,
            text=label,
            anchor="w",
            fg_color="transparent",
            text_color=theme.TEXT_SECONDARY,
            hover_color=theme.SURFACE_HOVER,
            height=38,
            corner_radius=theme.RADIUS_MD,
            font=theme.font_body(),
            command=lambda k=view_key: self._handle_click(k),
        )
        btn.pack(side="left", fill="x", expand=True)
        self._buttons[key] = btn

        if badge_key:
            badge = ctk.CTkLabel(
                btn_container,
                text="",
                font=theme.font_badge(),
                fg_color=theme.PRIMARY,
                text_color=theme.TEXT_PRIMARY,
                corner_radius=8,
                width=22,
                height=18,
            )
            # Hidden until counter > 0
            self._badges[badge_key] = badge

    def _handle_click(self, view_key: str) -> None:
        self.set_active(view_key)
        self.on_view_change(view_key)

    def set_active(self, active_key: str) -> None:
        """Highlight active navigation button."""
        self._active_key = active_key
        for key, btn in self._buttons.items():
            if key == active_key:
                btn.configure(
                    fg_color=theme.SURFACE_ACTIVE,
                    text_color=theme.TEXT_PRIMARY,
                    font=theme.font_body_bold(),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    text_color=theme.TEXT_SECONDARY,
                    font=theme.font_body(),
                )

    def update_badge(self, badge_key: str, count: int) -> None:
        """Update notification badge counter. Hides if count <= 0."""
        if badge_key not in self._badges:
            return
        badge = self._badges[badge_key]
        if count > 0:
            badge.configure(text=str(count))
            badge.pack(side="right", padx=(0, 8))
        else:
            badge.pack_forget()
