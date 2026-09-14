"""
Library View.

Canonical Library interface backed by SQLite SQL pagination.
Supports:
- Search (Title, Artist, Album)
- Filtering (ALL, OWNED, UNOWNED, DUPLICATES)
- Multi-selection & Select All Page
- Bulk Action: Preview Download Plan for selection
- Secondary Action: Import Existing Files (local MP3 folder scanner)
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
from ui import theme


class LibraryView(ctk.CTkFrame):
    """
    Paginated Canonical Library view with filters, search, and inspector dialogs.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_start_downloads: Optional[Callable[[List[int]], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.service = service
        self.on_start_downloads = on_start_downloads

        self.current_filter = "ALL"
        self.current_query = ""
        self.current_page = 1

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header & Search Toolbar ───────────────────────────
        header = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        hdr_box = ctk.CTkFrame(header, fg_color="transparent")
        hdr_box.pack(side="left", padx=24, pady=12)

        ctk.CTkLabel(
            hdr_box,
            text="📚  CANONICAL LIBRARY",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        # Search Box
        search_box = ctk.CTkFrame(header, fg_color="transparent")
        search_box.pack(side="right", padx=24, pady=14)

        self.search_var = tk.StringVar()
        self.search_entry = ctk.CTkEntry(
            search_box,
            textvariable=self.search_var,
            placeholder_text="Search title, artist, album…",
            width=280,
            height=36,
            font=theme.font_body(),
            fg_color=theme.SURFACE_MUTED,
            border_color=theme.BORDER,
            corner_radius=theme.RADIUS_MD,
        )
        self.search_entry.pack(side="left", padx=(0, 8))
        self.search_entry.bind("<Return>", lambda _e: self._on_search())

        ctk.CTkButton(
            search_box,
            text="Search",
            width=80,
            height=36,
            font=theme.font_body_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self._on_search,
        ).pack(side="left")

        # ── 2. Filter Tabs & Action Toolbar ──────────────────────────
        toolbar = ctk.CTkFrame(
            self,
            corner_radius=theme.RADIUS_LG,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        toolbar.grid(row=1, column=0, sticky="ew", padx=24, pady=(16, 12))

        tb_inner = ctk.CTkFrame(toolbar, fg_color="transparent")
        tb_inner.pack(fill="x", padx=16, pady=10)

        # State Filter Segmented Buttons
        self.filter_var = ctk.StringVar(value="ALL")
        self.filter_btn = ctk.CTkSegmentedButton(
            tb_inner,
            values=["ALL", "OWNED", "UNOWNED"],
            variable=self.filter_var,
            font=theme.font_caption_bold(),
            height=32,
            selected_color=theme.PRIMARY,
            command=self._on_filter_changed,
        )
        self.filter_btn.pack(side="left", padx=(0, 16))

        # Selection Helpers
        ctk.CTkButton(
            tb_inner,
            text="Select All Page",
            width=110,
            height=32,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_SM,
            command=self._select_all,
        ).pack(side="left", padx=3)

        ctk.CTkButton(
            tb_inner,
            text="Clear Selection",
            width=110,
            height=32,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_SM,
            command=self._clear_selection,
        ).pack(side="left", padx=3)

        # Right side actions
        right_actions = ctk.CTkFrame(tb_inner, fg_color="transparent")
        right_actions.pack(side="right")

        ctk.CTkButton(
            right_actions,
            text="📂 Import Existing Files",
            font=theme.font_caption_bold(),
            width=160,
            height=32,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=self._import_existing_files,
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            right_actions,
            text="⬇ Plan Selected Downloads",
            font=theme.font_caption_bold(),
            width=180,
            height=32,
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_BG,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            command=self._plan_selected_downloads,
        ).pack(side="left", padx=(4, 0))

        # ── 3. Table Area ───────────────────────────────────────────
        table_wrap = ctk.CTkFrame(self, fg_color="transparent")
        table_wrap.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
        table_wrap.grid_rowconfigure(0, weight=1)
        table_wrap.grid_columnconfigure(0, weight=1)

        self.table = SongTable(
            table_wrap,
            on_song_double_click=self._on_song_double_click,
            on_page_change=self._on_page_change,
            on_selection_change=self._on_selection_change,
        )
        self.table.grid(row=0, column=0, sticky="nsew")

        # Initial load
        self.refresh()

    def refresh(self) -> None:
        """Fetch and render data for current filter/query/page."""
        state_filter = None if self.current_filter == "ALL" else self.current_filter
        res = self.service.get_library_page(
            page=self.current_page,
            page_size=50,
            query=self.current_query or None,
            state=state_filter,
        )
        self.table.set_data(
            songs=res["songs"],
            total_items=res["total_items"],
            page=res["page"],
            total_pages=res["total_pages"],
        )

    def _on_search(self) -> None:
        self.current_query = self.search_var.get().strip()
        self.current_page = 1
        self.refresh()

    def _on_filter_changed(self, value: str) -> None:
        self.current_filter = value
        self.current_page = 1
        self.refresh()

    def _on_page_change(self, page: int) -> None:
        self.current_page = page
        self.refresh()

    def _on_selection_change(self, selected: List[LibrarySong]) -> None:
        pass

    def _select_all(self) -> None:
        self.table.select_all()

    def _clear_selection(self) -> None:
        self.table.clear_selection()

    def _on_song_double_click(self, song: LibrarySong) -> None:
        """Open detailed duplicate & metadata inspector dialog."""
        SongDetailsDialog(self.winfo_toplevel(), song=song, service=self.service)

    def _plan_selected_downloads(self) -> None:
        """Generate and preview download plan for selected songs."""
        selected = self.table.get_selected_songs()
        if not selected:
            return
        selected_ids = [s.id for s in selected if s.id is not None]
        plan = self.service.generate_download_plan(selected_ids)
        PlanPreviewDialog(
            self.winfo_toplevel(),
            plan=plan,
            on_confirm=self._on_plan_confirmed,
        )

    def _on_plan_confirmed(self, plan: Any) -> None:
        """Execute approved plan and trigger callback."""
        dl_ids = self.service.execute_download_plan(plan)
        if self.on_start_downloads and dl_ids:
            self.on_start_downloads(dl_ids)
        self.refresh()

    def _import_existing_files(self) -> None:
        """Open folder picker to import existing MP3 collection."""
        from tkinter import filedialog
        folder = filedialog.askdirectory(title="Select Music Folder to Import")
        if folder:
            count = self.service.import_local_folder(folder)
            self.refresh()
