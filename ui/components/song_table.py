"""
SongTable component for rendering tabular song lists with modern dark styling and SQL pagination.

Uses ttk.Treeview combined with SQL pagination controls for responsive loading of large libraries.
"""

from typing import Dict, List, Optional, Any, Callable
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from library.models import LibrarySong, SongState
from ui import theme


class SongTable(ctk.CTkFrame):
    """
    Paginated table component using ttk.Treeview with SQL-backed page navigation controls.
    """

    def __init__(
        self,
        master: Any,
        on_song_double_click: Optional[Callable[[LibrarySong], None]] = None,
        on_page_change: Optional[Callable[[int], None]] = None,
        on_selection_change: Optional[Callable[[List[LibrarySong]], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.on_song_double_click = on_song_double_click
        self.on_page_change = on_page_change
        self.on_selection_change = on_selection_change

        self.current_page = 1
        self.total_pages = 1
        self.total_items = 0
        self.page_size = 50
        self._songs_map: Dict[str, LibrarySong] = {}

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Treeview Frame ─────────────────────────────────────────
        table_container = ctk.CTkFrame(
            self,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        table_container.grid(row=0, column=0, sticky="nsew")
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # Style Treeview for Dark Mode
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "SongTree.Treeview",
            background=theme.SURFACE,
            foreground=theme.TEXT_PRIMARY,
            fieldbackground=theme.SURFACE,
            rowheight=34,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        style.configure(
            "SongTree.Treeview.Heading",
            background=theme.SURFACE_ELEVATED,
            foreground=theme.TEXT_SECONDARY,
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map(
            "SongTree.Treeview",
            background=[("selected", theme.PRIMARY)],
            foreground=[("selected", theme.TEXT_PRIMARY)],
        )

        columns = ("id", "title", "artist", "album", "year", "quality", "state", "source")
        self.tree = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            selectmode="extended",
            style="SongTree.Treeview",
        )

        # Heading Setup & Column Widths
        self.tree.heading("id", text="#")
        self.tree.heading("title", text="Title")
        self.tree.heading("artist", text="Artist")
        self.tree.heading("album", text="Album / Movie")
        self.tree.heading("year", text="Year")
        self.tree.heading("quality", text="Bitrate")
        self.tree.heading("state", text="Status")
        self.tree.heading("source", text="Source")

        self.tree.column("id", width=45, minwidth=35, anchor="center")
        self.tree.column("title", width=260, minwidth=150, anchor="w")
        self.tree.column("artist", width=180, minwidth=100, anchor="w")
        self.tree.column("album", width=180, minwidth=100, anchor="w")
        self.tree.column("year", width=65, minwidth=50, anchor="center")
        self.tree.column("quality", width=95, minwidth=70, anchor="center")
        self.tree.column("state", width=105, minwidth=80, anchor="center")
        self.tree.column("source", width=130, minwidth=80, anchor="w")

        self.tree.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        # Scrollbar
        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(0, 2), pady=2)
        self.tree.configure(yscrollcommand=vsb.set)

        # Bind events
        self.tree.bind("<Double-1>", self._handle_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._handle_select)

        # ── SQL Pagination Control Bar ──────────────────────────────
        self.pagi_frame = ctk.CTkFrame(
            self,
            height=44,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        self.pagi_frame.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        self.pagi_frame.grid_columnconfigure(3, weight=1)

        self.btn_first = ctk.CTkButton(
            self.pagi_frame,
            text="« First",
            width=65,
            height=28,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_SM,
            command=self._go_first,
        )
        self.btn_first.grid(row=0, column=0, padx=(12, 2), pady=8)

        self.btn_prev = ctk.CTkButton(
            self.pagi_frame,
            text="‹ Prev",
            width=65,
            height=28,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_SM,
            command=self._go_prev,
        )
        self.btn_prev.grid(row=0, column=1, padx=2, pady=8)

        self.btn_next = ctk.CTkButton(
            self.pagi_frame,
            text="Next ›",
            width=65,
            height=28,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_SM,
            command=self._go_next,
        )
        self.btn_next.grid(row=0, column=2, padx=2, pady=8)

        self.pagi_info_var = tk.StringVar(value="Page 1 of 1 (0 items)")
        self.pagi_info_label = ctk.CTkLabel(
            self.pagi_frame,
            textvariable=self.pagi_info_var,
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="center",
        )
        self.pagi_info_label.grid(row=0, column=3, sticky="ew", padx=8, pady=8)

        self.btn_last = ctk.CTkButton(
            self.pagi_frame,
            text="Last »",
            width=65,
            height=28,
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            corner_radius=theme.RADIUS_SM,
            command=self._go_last,
        )
        self.btn_last.grid(row=0, column=4, padx=(2, 12), pady=8)

    def set_data(
        self,
        songs: List[LibrarySong],
        total_items: int,
        page: int,
        total_pages: int,
    ) -> None:
        """Populate Treeview with page slice."""
        self.current_page = page
        self.total_pages = max(1, total_pages)
        self.total_items = total_items
        self._songs_map.clear()

        for row in self.tree.get_children():
            self.tree.delete(row)

        for song in songs:
            song_id_str = str(song.id)
            self._songs_map[song_id_str] = song

            state_badge = "✓ Downloaded" if song.state == SongState.OWNED else "Not Downloaded"
            quality_str = f"{song.bitrate_kbps} kbps" if song.bitrate_kbps else "320 kbps"
            year_str = str(song.year) if song.year else "--"

            self.tree.insert(
                "",
                "end",
                iid=song_id_str,
                values=(
                    song.id,
                    song.title,
                    song.artist or "--",
                    song.album or "--",
                    year_str,
                    quality_str,
                    state_badge,
                    song.source_site or "Library",
                ),
            )

        self.pagi_info_var.set(
            f"Page {self.current_page} of {self.total_pages} ({self.total_items:,} songs)"
        )
        self._update_button_states()

    def get_selected_songs(self) -> List[LibrarySong]:
        """Return list of selected songs."""
        selected_iids = self.tree.selection()
        return [self._songs_map[iid] for iid in selected_iids if iid in self._songs_map]

    def select_all(self) -> None:
        """Select all items currently rendered on the page."""
        all_iids = self.tree.get_children()
        self.tree.selection_set(all_iids)
        self._handle_select(None)

    def clear_selection(self) -> None:
        """Deselect all rows."""
        self.tree.selection_remove(self.tree.selection())
        self._handle_select(None)

    def _handle_double_click(self, _event) -> None:
        selected_iids = self.tree.selection()
        if selected_iids and self.on_song_double_click:
            iid = selected_iids[0]
            if iid in self._songs_map:
                self.on_song_double_click(self._songs_map[iid])

    def _handle_select(self, _event) -> None:
        if self.on_selection_change:
            self.on_selection_change(self.get_selected_songs())

    def _go_first(self) -> None:
        if self.current_page > 1 and self.on_page_change:
            self.on_page_change(1)

    def _go_prev(self) -> None:
        if self.current_page > 1 and self.on_page_change:
            self.on_page_change(self.current_page - 1)

    def _go_next(self) -> None:
        if self.current_page < self.total_pages and self.on_page_change:
            self.on_page_change(self.current_page + 1)

    def _go_last(self) -> None:
        if self.current_page < self.total_pages and self.on_page_change:
            self.on_page_change(self.total_pages)

    def _update_button_states(self) -> None:
        prev_state = "normal" if self.current_page > 1 else "disabled"
        next_state = "normal" if self.current_page < self.total_pages else "disabled"
        self.btn_first.configure(state=prev_state)
        self.btn_prev.configure(state=prev_state)
        self.btn_next.configure(state=next_state)
        self.btn_last.configure(state=next_state)
