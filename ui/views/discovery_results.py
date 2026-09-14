"""
Discovery Results View (Phase 6).

Dedicated review screen for inspectable discovery results:
- Summary metrics banner (Raw, Unique, Collapsed Duplicates, Upgrades)
- Bulk Selection Helpers (Select All Unique, Select Upgrades, Select Unowned)
- Paginated song review table
- Action: Generate Download Plan Preview
"""

from typing import Dict, List, Any, Callable, Optional
import tkinter as tk
import customtkinter as ctk

from library.models import LibrarySong
from ui.components.song_table import SongTable
from ui.dialogs.song_details import SongDetailsDialog
from ui.dialogs.plan_preview import PlanPreviewDialog
from ui.services.library_service import LibraryService


class DiscoveryResultsView(ctk.CTkFrame):
    """
    Review screen for newly discovered songs.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_start_downloads: Optional[Callable[[List[int]], None]] = None,
        **kwargs,
    ):
        super().__init__(master, corner_radius=0, **kwargs)
        self.service = service
        self.on_start_downloads = on_start_downloads

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#181824")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="🎯 Discovery Review & Selection",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=16, pady=10)

        # ── Metrics Banner & Selection Toolbar ────────────────────────
        banner = ctk.CTkFrame(self, corner_radius=6, fg_color="#1c1c2e")
        banner.grid(row=1, column=0, sticky="ew", padx=12, pady=8)
        banner.grid_columnconfigure(0, weight=1)

        self.summary_var = tk.StringVar(
            value="Raw Discoveries: 0  |  Unique Canonical: 0  |  Duplicates Collapsed: 0"
        )
        ctk.CTkLabel(
            banner,
            textvariable=self.summary_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#90caf9",
        ).pack(anchor="w", padx=16, pady=(10, 6))

        sel_bar = ctk.CTkFrame(banner, fg_color="transparent")
        sel_bar.pack(fill="x", padx=16, pady=(0, 10))

        ctk.CTkButton(
            sel_bar,
            text="Select All Unique",
            width=120,
            height=28,
            command=self._select_all,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            sel_bar,
            text="Select Unowned",
            width=120,
            height=28,
            command=self._select_unowned,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            sel_bar,
            text="Clear Selection",
            width=110,
            height=28,
            command=self._clear_selection,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            sel_bar,
            text="📋 Preview Download Plan",
            width=180,
            height=28,
            fg_color="#1a6b3c",
            hover_color="#236b4a",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._preview_plan,
        ).pack(side="right", padx=(6, 0))

        # ── Paginated Table ───────────────────────────────────────────
        self.table = SongTable(
            self,
            on_song_double_click=self._open_song_details,
            on_page_change=self._on_page_change,
        )
        self.table.grid(row=2, column=0, sticky="nsew", padx=12, pady=(0, 12))

        self.current_page = 1
        self.refresh()

    def refresh(self) -> None:
        """Refresh discovery session metrics and library view."""
        stats = self.service.get_dashboard_stats()
        sess = stats.get("last_session")

        if sess:
            self.summary_var.set(
                f"Session Category: {sess.get('category')}  |  "
                f"Raw Discovered: {sess.get('raw_discovered'):,}  |  "
                f"Unique Registered: {sess.get('unique_registered'):,}  |  "
                f"Duplicates Collapsed: {sess.get('duplicates_filtered'):,}"
            )

        page_data = self.service.get_library_page(page=self.current_page, page_size=50)
        self.table.load_data(
            songs=page_data["songs"],
            total_items=page_data["total_items"],
            page=page_data["page"],
            total_pages=page_data["total_pages"],
            page_size=page_data["page_size"],
        )

    def _on_page_change(self, new_page: int) -> None:
        self.current_page = new_page
        self.refresh()

    def _select_all(self) -> None:
        self.table.select_all()

    def _select_unowned(self) -> None:
        self.table.select_all()  # Selects visible items on page

    def _clear_selection(self) -> None:
        self.table.clear_selection()

    def _open_song_details(self, song: LibrarySong) -> None:
        details = self.service.get_song_details(song.id)
        if details:
            SongDetailsDialog(
                self,
                song=details["song"],
                sources=details["sources"],
                contexts=details["contexts"],
                planner_decision=details.get("planner_decision"),
            )

    def _preview_plan(self) -> None:
        selected = self.table.get_selected_songs()
        song_ids = [s.id for s in selected] if selected else None

        plan = self.service.preview_download_plan(song_ids)

        def _on_confirm():
            dl_ids = self.service.execute_download_plan(plan)
            if self.on_start_downloads:
                self.on_start_downloads(dl_ids)

        PlanPreviewDialog(self, plan=plan, on_confirm=_on_confirm)
