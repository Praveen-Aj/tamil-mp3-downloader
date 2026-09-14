"""
Library View (Phase 3).

Canonical Library interface backed by SQLite SQL pagination.
Supports:
- Search (Title, Artist, Album)
- Filtering (ALL, OWNED, UNOWNED)
- Multi-selection & Select All
- Bulk Action: Preview Download Plan for selection
- Double-click to open Song Details / Duplicate Inspector
"""

from typing import Dict, List, Any, Callable, Optional
import tkinter as tk
import customtkinter as ctk

from library.models import LibrarySong
from ui.components.song_table import SongTable
from ui.dialogs.song_details import SongDetailsDialog
from ui.dialogs.plan_preview import PlanPreviewDialog
from ui.services.library_service import LibraryService


class LibraryView(ctk.CTkFrame):
    """
    Paginated Canonical Library view.
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

        self.current_filter = "ALL"
        self.current_query = ""
        self.current_page = 1

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Search & Filter Toolbar ───────────────────────────
        toolbar = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#181824")
        toolbar.grid(row=0, column=0, sticky="ew")
        toolbar.grid_propagate(False)

        ctk.CTkLabel(
            toolbar, text="📚 Canonical Library", font=ctk.CTkFont(size=16, weight="bold")
        ).pack(side="left", padx=(16, 12))

        # Search Entry
        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(
            toolbar,
            textvariable=self.search_var,
            placeholder_text="Search title, artist, album…",
            width=260,
            height=32,
        )
        self.search_entry.pack(side="left", padx=6)
        self.search_entry.bind("<Return>", lambda _e: self._on_search())

        ctk.CTkButton(
            toolbar, text="Search", width=75, height=32, command=self._on_search
        ).pack(side="left", padx=4)

        # State Filter Segmented Button
        self.filter_var = ctk.StringVar(value="ALL")
        self.filter_btn = ctk.CTkSegmentedButton(
            toolbar,
            values=["ALL", "OWNED", "UNOWNED"],
            variable=self.filter_var,
            command=self._on_filter_changed,
        )
        self.filter_btn.pack(side="left", padx=16)

        # ── 2. Bulk Action Bar ────────────────────────────────────────
        bulk_bar = ctk.CTkFrame(self, height=42, corner_radius=0, fg_color="#202030")
        bulk_bar.grid(row=1, column=0, sticky="ew")
        bulk_bar.grid_propagate(False)

        ctk.CTkButton(
            bulk_bar, text="Select All Page", width=110, height=28, command=self._select_all
        ).pack(side="left", padx=(16, 4), pady=7)

        ctk.CTkButton(
            bulk_bar, text="Clear Selection", width=110, height=28, command=self._clear_selection
        ).pack(side="left", padx=4, pady=7)

        ctk.CTkButton(
            bulk_bar,
            text="⬇ Plan Selected Downloads",
            width=180,
            height=28,
            fg_color="#1a6b3c",
            hover_color="#236b4a",
            command=self._plan_selected_downloads,
        ).pack(side="left", padx=12, pady=7)

        self.sel_count_var = tk.StringVar(value="0 songs selected")
        ctk.CTkLabel(
            bulk_bar,
            textvariable=self.sel_count_var,
            font=ctk.CTkFont(size=11),
            text_color="#aaaaaa",
        ).pack(side="right", padx=16, pady=7)

        # ── 3. Paginated Song Table Component ─────────────────────────
        self.table = SongTable(
            self,
            on_song_double_click=self._open_song_details,
            on_page_change=self._on_page_change,
            on_selection_change=self._on_selection_change,
        )
        self.table.grid(row=2, column=0, sticky="nsew", padx=6, pady=6)

        self.refresh()

    def refresh(self) -> None:
        """Fetch current SQL page slice and populate table."""
        page_data = self.service.get_library_page(
            query=self.current_query,
            state_filter=self.current_filter,
            page=self.current_page,
            page_size=50,
        )

        self.table.load_data(
            songs=page_data["songs"],
            total_items=page_data["total_items"],
            page=page_data["page"],
            total_pages=page_data["total_pages"],
            page_size=page_data["page_size"],
        )

    def _on_search(self) -> None:
        self.current_query = self.search_var.get().strip()
        self.current_page = 1
        self.refresh()

    def _on_filter_changed(self, value: str) -> None:
        self.current_filter = value
        self.current_page = 1
        self.refresh()

    def _on_page_change(self, new_page: int) -> None:
        self.current_page = new_page
        self.refresh()

    def _on_selection_change(self, selected_songs: List[LibrarySong]) -> None:
        self.sel_count_var.set(f"{len(selected_songs):,} songs selected")

    def _select_all(self) -> None:
        self.table.select_all()

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

    def _plan_selected_downloads(self) -> None:
        selected = self.table.get_selected_songs()
        song_ids = [s.id for s in selected] if selected else None

        plan = self.service.preview_download_plan(song_ids)

        def _on_confirm():
            dl_ids = self.service.execute_download_plan(plan)
            if self.on_start_downloads:
                self.on_start_downloads(dl_ids)

        PlanPreviewDialog(self, plan=plan, on_confirm=_on_confirm)
