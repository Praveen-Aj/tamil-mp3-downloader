"""
SongTable component for rendering tabular song lists with dark styling and SQL pagination.

Uses ttk.Treeview combined with SQL pagination controls for responsive loading of large libraries (1,000+ to 10,000+ songs).
"""

from typing import Dict, List, Optional, Any, Callable
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from library.models import LibrarySong, SongState


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
        super().__init__(master, **kwargs)
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
        table_container = ctk.CTkFrame(self, corner_radius=0)
        table_container.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)
        table_container.grid_rowconfigure(0, weight=1)
        table_container.grid_columnconfigure(0, weight=1)

        # Style Treeview for Dark Mode
        style = ttk.Style()
        style.theme_use("default")
        style.configure(
            "SongTree.Treeview",
            background="#1c1c2e",
            foreground="#e0e0e0",
            fieldbackground="#1c1c2e",
            rowheight=28,
            font=("Segoe UI", 10),
            borderwidth=0,
        )
        style.configure(
            "SongTree.Treeview.Heading",
            background="#252538",
            foreground="#aaaacc",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
        )
        style.map(
            "SongTree.Treeview",
            background=[("selected", "#1f538d")],
            foreground=[("selected", "#ffffff")],
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
        self.tree.heading("id", text="ID")
        self.tree.heading("title", text="Title")
        self.tree.heading("artist", text="Artist")
        self.tree.heading("album", text="Album / Movie")
        self.tree.heading("year", text="Year")
        self.tree.heading("quality", text="Quality")
        self.tree.heading("state", text="State")
        self.tree.heading("source", text="Source")

        self.tree.column("id", width=50, minwidth=40, anchor="center")
        self.tree.column("title", width=220, minwidth=140, anchor="w")
        self.tree.column("artist", width=180, minwidth=100, anchor="w")
        self.tree.column("album", width=180, minwidth=100, anchor="w")
        self.tree.column("year", width=60, minwidth=50, anchor="center")
        self.tree.column("quality", width=90, minwidth=70, anchor="center")
        self.tree.column("state", width=90, minwidth=70, anchor="center")
        self.tree.column("source", width=110, minwidth=80, anchor="w")

        self.tree.grid(row=0, column=0, sticky="nsew")

        # Scrollbar
        vsb = ttk.Scrollbar(table_container, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        # Bind events
        self.tree.bind("<Double-1>", self._handle_double_click)
        self.tree.bind("<<TreeviewSelect>>", self._handle_select)

        # ── SQL Pagination Control Bar ──────────────────────────────
        self.pagi_frame = ctk.CTkFrame(self, height=40, corner_radius=0)
        self.pagi_frame.grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        self.pagi_frame.grid_columnconfigure(3, weight=1)

        self.btn_first = ctk.CTkButton(
            self.pagi_frame, text="« First", width=65, height=28, command=self._go_first
        )
        self.btn_first.grid(row=0, column=0, padx=(8, 2), pady=6)

        self.btn_prev = ctk.CTkButton(
            self.pagi_frame, text="‹ Prev", width=65, height=28, command=self._go_prev
        )
        self.btn_prev.grid(row=0, column=1, padx=2, pady=6)

        self.btn_next = ctk.CTkButton(
            self.pagi_frame, text="Next ›", width=65, height=28, command=self._go_next
        )
        self.btn_next.grid(row=0, column=2, padx=2, pady=6)

        self.btn_last = ctk.CTkButton(
            self.pagi_frame, text="Last »", width=65, height=28, command=self._go_last
        )
        self.btn_last.grid(row=0, column=4, padx=2, pady=6)

        self.pagi_info_var = tk.StringVar(value="Page 1 of 1 (0 items)")
        self.pagi_info_label = ctk.CTkLabel(
            self.pagi_frame,
            textvariable=self.pagi_info_var,
            font=ctk.CTkFont(size=11),
            text_color="#aaaaaa",
        )
        self.pagi_info_label.grid(row=0, column=3, padx=12, pady=6)

    # ── Population & SQL Pagination ─────────────────────────────
    def load_data(
        self,
        songs: List[LibrarySong],
        total_items: int,
        page: int,
        total_pages: int,
        page_size: int = 50,
    ) -> None:
        """Populate current page slice of songs fetched via SQL query."""
        self.current_page = page
        self.total_pages = total_pages
        self.total_items = total_items
        self.page_size = page_size
        self._songs_map.clear()

        # Clear existing tree items
        for item in self.tree.get_children():
            self.tree.delete(item)

        for song in songs:
            item_id = str(song.id)
            self._songs_map[item_id] = song

            year_str = str(song.year) if song.year else "-"
            quality_str = f"{song.quality_kbps} kbps" if song.quality_kbps else "Unknown"
            state_str = "OWNED" if song.state == SongState.OWNED else "UNOWNED"
            primary_src = getattr(song, "primary_source_name", None) or getattr(song, "source_name", None) or "-"

            # Tag for styling owned vs unowned
            tag = "owned" if song.state == SongState.OWNED else "unowned"

            self.tree.insert(
                "",
                "end",
                iid=item_id,
                values=(
                    song.id,
                    song.title,
                    song.artist,
                    song.album or "-",
                    year_str,
                    quality_str,
                    state_str,
                    primary_src,
                ),
                tags=(tag,),
            )

        self.tree.tag_configure("owned", foreground="#81c784")
        self.tree.tag_configure("unowned", foreground="#e0e0e0")

        # Update pagination UI
        self.pagi_info_var.set(
            f"Page {page} of {max(1, total_pages)}  ({total_items:,} songs total, SQL paginated)"
        )
        self.btn_first.configure(state="normal" if page > 1 else "disabled")
        self.btn_prev.configure(state="normal" if page > 1 else "disabled")
        self.btn_next.configure(state="normal" if page < total_pages else "disabled")
        self.btn_last.configure(state="normal" if page < total_pages else "disabled")

    # ── Selection & Double-Click ─────────────────────────────────
    def get_selected_songs(self) -> List[LibrarySong]:
        """Return list of selected LibrarySong objects."""
        selected_iids = self.tree.selection()
        return [self._songs_map[iid] for iid in selected_iids if iid in self._songs_map]

    def select_all(self) -> None:
        """Select all items visible on the current page."""
        self.tree.selection_set(self.tree.get_children())

    def clear_selection(self) -> None:
        """Clear selection."""
        self.tree.selection_remove(self.tree.selection())

    def _handle_double_click(self, event: Any) -> None:
        selected = self.get_selected_songs()
        if selected and self.on_song_double_click:
            self.on_song_double_click(selected[0])

    def _handle_select(self, event: Any) -> None:
        if self.on_selection_change:
            self.on_selection_change(self.get_selected_songs())

    # ── Page Change Triggers ─────────────────────────────────────
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
