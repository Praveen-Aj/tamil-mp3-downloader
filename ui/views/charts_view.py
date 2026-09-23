"""
Charts & Top 100 Discovery and Library View.

Provides:
- Directory of Curated Charts: Top 100, Trending, Streaming Hits, Evergreen Classics
- Filter by Chart Type: All, Top 100, Trending, Stream Hits, Classics
- Instant debounced search
- Aggregated chart metrics: Total Songs, Downloaded Count, Missing Count
- Live sync button to refresh charts from external providers
- Clickable cards opening ChartDetailView
"""

import threading
from typing import Dict, List, Any, Callable, Optional
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from ui.services.library_service import LibraryService
from ui import theme


class ChartsView(ctk.CTkFrame):
    """
    Curated Charts & Top 100 Directory View.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_open_chart: Callable[[str], None],
        on_navigate: Optional[Callable[[str], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color=theme.BG_APP, corner_radius=0, **kwargs)
        self.service = service
        self.on_open_chart = on_open_chart
        self.on_navigate = on_navigate

        self.current_query = ""
        self.current_type: str = "all"  # 'all', 'top_100', 'trending', 'stream_top', 'all_time'
        self.current_page = 1
        self.page_size = 12
        self._search_debounce_id: Optional[str] = None
        self._current_charts: List[Dict[str, Any]] = []
        self._total_charts: int = 0
        self._is_syncing: bool = False

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header Toolbar ────────────────────────────────────
        header = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        hdr_box = ctk.CTkFrame(header, fg_color="transparent")
        hdr_box.pack(side="left", padx=20, pady=10)

        title_lbl = ctk.CTkLabel(
            hdr_box,
            text="🔥 Curated Charts & Top 100",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        )
        title_lbl.pack(side="left")

        # Sync button
        self.sync_btn = ctk.CTkButton(
            header,
            text="🔄 Sync Charts",
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_CARD,
            hover_color=theme.PRIMARY_MUTED,
            text_color=theme.PRIMARY_LIGHT,
            corner_radius=theme.RADIUS_SM,
            height=32,
            width=115,
            command=self._on_sync_clicked,
        )
        self.sync_btn.pack(side="right", padx=20, pady=12)

        # ── 2. Filter Bar (Type Tabs & Search) ────────────────────────
        filter_bar = ctk.CTkFrame(self, height=48, corner_radius=0, fg_color=theme.BG_SIDEBAR)
        filter_bar.grid(row=1, column=0, sticky="ew", padx=0, pady=0)
        filter_bar.grid_propagate(False)

        # Chart Type Filter Tabs
        tabs_box = ctk.CTkFrame(filter_bar, fg_color="transparent")
        tabs_box.pack(side="left", padx=(20, 10), pady=8)

        self._type_buttons: Dict[str, ctk.CTkButton] = {}
        types = [
            ("all", "All Charts"),
            ("top_100", "🏆 Top 100"),
            ("trending", "🔥 Trending"),
            ("stream_top", "🍎 Streaming Hits"),
            ("all_time", "📻 Classics"),
        ]

        for type_key, label in types:
            btn = ctk.CTkButton(
                tabs_box,
                text=label,
                font=theme.font_caption_bold(),
                corner_radius=theme.RADIUS_FULL,
                height=30,
                width=80 if len(label) < 10 else 110,
                fg_color=theme.PRIMARY if type_key == "all" else "transparent",
                text_color=theme.TEXT_PRIMARY if type_key == "all" else theme.TEXT_MUTED,
                hover_color=theme.PRIMARY_MUTED,
                command=lambda tk=type_key: self._on_type_tab_clicked(tk),
            )
            btn.pack(side="left", padx=(0, 6))
            self._type_buttons[type_key] = btn

        # Search Bar
        search_box = ctk.CTkFrame(filter_bar, fg_color="transparent")
        search_box.pack(side="right", padx=20, pady=8)

        self.search_entry = ctk.CTkEntry(
            search_box,
            placeholder_text="Search charts by title or provider...",
            font=theme.font_body(),
            width=280,
            height=32,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.BG_INPUT,
            border_color=theme.BORDER,
            text_color=theme.TEXT_PRIMARY,
        )
        self.search_entry.pack(side="right")
        self.search_entry.bind("<KeyRelease>", self._on_search_key)

        # ── 3. Scrollable Cards Grid Container ───────────────────────
        self.scroll_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
            corner_radius=0,
        )
        self.scroll_frame.grid(row=2, column=0, sticky="nsew", padx=20, pady=(15, 10))
        for col in range(3):
            self.scroll_frame.grid_columnconfigure(col, weight=1, uniform="charts_col")

        # ── 4. Bottom Pagination Bar ─────────────────────────────────
        self.pagination_bar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color=theme.BG_HEADER)
        self.pagination_bar.grid(row=3, column=0, sticky="ew")
        self.pagination_bar.grid_propagate(False)

        self.page_info_lbl = ctk.CTkLabel(
            self.pagination_bar,
            text="",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        )
        self.page_info_lbl.pack(side="left", padx=20, pady=10)

        nav_btns = ctk.CTkFrame(self.pagination_bar, fg_color="transparent")
        nav_btns.pack(side="right", padx=20, pady=6)

        self.first_btn = ctk.CTkButton(
            nav_btns, text="« First", width=65, height=28,
            font=theme.font_caption(), fg_color=theme.SURFACE_CARD,
            command=lambda: self._go_page(1)
        )
        self.first_btn.pack(side="left", padx=2)

        self.prev_btn = ctk.CTkButton(
            nav_btns, text="‹ Prev", width=60, height=28,
            font=theme.font_caption(), fg_color=theme.SURFACE_CARD,
            command=lambda: self._go_page(self.current_page - 1)
        )
        self.prev_btn.pack(side="left", padx=2)

        self.page_num_lbl = ctk.CTkLabel(
            nav_btns, text="1", font=theme.font_caption_bold(), width=40,
            text_color=theme.TEXT_PRIMARY
        )
        self.page_num_lbl.pack(side="left", padx=4)

        self.next_btn = ctk.CTkButton(
            nav_btns, text="Next ›", width=60, height=28,
            font=theme.font_caption(), fg_color=theme.SURFACE_CARD,
            command=lambda: self._go_page(self.current_page + 1)
        )
        self.next_btn.pack(side="left", padx=2)

        # Initial data load
        self.refresh()

    def refresh(self) -> None:
        """Fetch current page of charts and render."""
        type_filter = None if self.current_type == "all" else self.current_type
        charts, total = self.service.get_charts_page(
            query=self.current_query,
            chart_type=type_filter,
            page=self.current_page,
            page_size=self.page_size,
        )
        self._apply_charts_data(charts, total)

    def _apply_charts_data(self, charts: List[Dict[str, Any]], total: int) -> None:
        self._current_charts = charts
        self._total_charts = total

        # Clear existing cards
        for w in self.scroll_frame.winfo_children():
            w.destroy()

        if not charts:
            self._render_empty_state()
            self._update_pagination(0)
            return

        for idx, chart in enumerate(charts):
            row = idx // 3
            col = idx % 3
            card = self._create_chart_card(self.scroll_frame, chart)
            card.grid(row=row, column=col, sticky="nsew", padx=8, pady=8)

        self._update_pagination(total)

    def _create_chart_card(self, parent: Any, chart: Dict[str, Any]) -> ctk.CTkFrame:
        """Build an interactive card representing a chart snapshot."""
        card = ctk.CTkFrame(
            parent,
            fg_color=theme.SURFACE_CARD,
            corner_radius=theme.RADIUS_MD,
            border_width=1,
            border_color=theme.BORDER,
        )

        c_type = chart.get("chart_type", "top_100")
        icon = "🏆"
        badge_text = "Top Chart"
        if c_type == "trending":
            icon = "🔥"
            badge_text = "Trending"
        elif c_type == "stream_top":
            icon = "🍎"
            badge_text = "Streaming"
        elif c_type == "all_time":
            icon = "📻"
            badge_text = "Classics"

        # Hover feedback
        card.bind("<Enter>", lambda e: card.configure(border_color=theme.BORDER_LIGHT))
        card.bind("<Leave>", lambda e: card.configure(border_color=theme.BORDER))

        # Card Header
        top_box = ctk.CTkFrame(card, fg_color="transparent")
        top_box.pack(fill="x", padx=14, pady=(14, 6))

        icon_frame = ctk.CTkFrame(
            top_box,
            width=42,
            height=42,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE_ELEVATED,
        )
        icon_frame.pack(side="left", padx=(0, 10))
        icon_frame.pack_propagate(False)

        icon_lbl = ctk.CTkLabel(icon_frame, text="")
        icon_lbl.pack(expand=True, fill="both")

        chart_cover = chart.get("cover_url") or chart.get("image_url")
        self.service.artwork.bind_artwork(
            widget=icon_lbl,
            source=chart_cover,
            size=(42, 42),
            entity_type="chart",
            fallback_text=chart.get("title"),
        )

        title_box = ctk.CTkFrame(top_box, fg_color="transparent")
        title_box.pack(side="left", fill="both", expand=True)

        title = chart.get("title", "Untitled Chart")
        title_lbl = ctk.CTkLabel(
            title_box,
            text=title,
            font=theme.font_body_bold(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
            wraplength=200,
            justify="left",
        )
        title_lbl.pack(anchor="w")

        provider = chart.get("provider_name", "").replace("_", " ").title()
        provider_lbl = ctk.CTkLabel(
            title_box,
            text=f"{provider} • {badge_text}",
            font=theme.font_caption(),
            text_color=theme.PRIMARY_LIGHT,
            anchor="w",
        )
        provider_lbl.pack(anchor="w")

        # Snapshot Date
        snap_raw = chart.get("snapshot_date", "")
        date_str = str(snap_raw).split("T")[0] if snap_raw else "Recent"
        date_lbl = ctk.CTkLabel(
            card,
            text=f"Updated: {date_str}",
            font=theme.font_badge(),
            text_color=theme.TEXT_DIM,
            anchor="w",
        )
        date_lbl.pack(fill="x", padx=16, pady=(0, 6))

        # Metrics Pills Frame
        stats_frame = ctk.CTkFrame(card, fg_color=theme.BG_SIDEBAR, corner_radius=theme.RADIUS_SM)
        stats_frame.pack(fill="x", padx=14, pady=(4, 12))

        tot_songs = chart.get("total_entries", 0)
        dl_songs = chart.get("downloaded_entries", 0)
        miss_songs = chart.get("missing_entries", 0)

        # Total Songs pill
        s1 = ctk.CTkFrame(stats_frame, fg_color="transparent")
        s1.pack(side="left", expand=True, fill="x", pady=6)
        ctk.CTkLabel(s1, text=str(tot_songs), font=theme.font_body_bold(), text_color=theme.TEXT_PRIMARY).pack()
        ctk.CTkLabel(s1, text="Tracks", font=theme.font_badge(), text_color=theme.TEXT_MUTED).pack()

        # Downloaded pill
        s2 = ctk.CTkFrame(stats_frame, fg_color="transparent")
        s2.pack(side="left", expand=True, fill="x", pady=6)
        ctk.CTkLabel(s2, text=f"✓ {dl_songs}", font=theme.font_body_bold(), text_color=theme.SUCCESS).pack()
        ctk.CTkLabel(s2, text="Downloaded", font=theme.font_badge(), text_color=theme.SUCCESS).pack()

        # Missing pill
        s3 = ctk.CTkFrame(stats_frame, fg_color="transparent")
        s3.pack(side="left", expand=True, fill="x", pady=6)
        ctk.CTkLabel(s3, text=str(miss_songs), font=theme.font_body_bold(), text_color=theme.WARNING).pack()
        ctk.CTkLabel(s3, text="Missing", font=theme.font_badge(), text_color=theme.WARNING).pack()

        # Action Button
        chart_id = chart.get("id", "")
        btn = ctk.CTkButton(
            card,
            text="View Chart →",
            font=theme.font_caption_bold(),
            fg_color=theme.PRIMARY_MUTED,
            hover_color=theme.PRIMARY,
            text_color=theme.TEXT_PRIMARY,
            corner_radius=theme.RADIUS_SM,
            height=30,
            command=lambda cid=chart_id: self.on_open_chart(cid),
        )
        btn.pack(fill="x", padx=14, pady=(0, 14))

        return card

    def _render_empty_state(self) -> None:
        empty_box = ctk.CTkFrame(self.scroll_frame, fg_color="transparent")
        empty_box.grid(row=0, column=0, columnspan=3, pady=60)

        ctk.CTkLabel(
            empty_box,
            text="📻",
            font=ctk.CTkFont(size=48),
        ).pack(pady=(0, 12))

        ctk.CTkLabel(
            empty_box,
            text="No Charts Found",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(pady=(0, 6))

        ctk.CTkLabel(
            empty_box,
            text="No charts match the current filter or search criteria.\nClick 'Sync Charts' to retrieve live charts from providers.",
            font=theme.font_body(),
            text_color=theme.TEXT_MUTED,
            justify="center",
        ).pack(pady=(0, 16))

        ctk.CTkButton(
            empty_box,
            text="🔄 Sync Charts",
            font=theme.font_button(),
            fg_color=theme.PRIMARY,
            command=self._on_sync_clicked,
        ).pack()

    def _on_type_tab_clicked(self, type_key: str) -> None:
        self.current_type = type_key
        self.current_page = 1
        for tk, btn in self._type_buttons.items():
            if tk == type_key:
                btn.configure(fg_color=theme.PRIMARY, text_color=theme.TEXT_PRIMARY)
            else:
                btn.configure(fg_color="transparent", text_color=theme.TEXT_MUTED)
        self.refresh()

    def _on_search_key(self, event=None) -> None:
        if self._search_debounce_id:
            self.after_cancel(self._search_debounce_id)
        self._search_debounce_id = self.after(300, self._apply_search)

    def _apply_search(self) -> None:
        self.current_query = self.search_entry.get().strip()
        self.current_page = 1
        self.refresh()

    def _on_sync_clicked(self) -> None:
        if self._is_syncing:
            return
        self._is_syncing = True
        self.sync_btn.configure(text="Syncing...", state="disabled")

        def worker():
            try:
                synced = self.service.sync_charts()
                msg = f"Successfully synced {len(synced)} charts."
            except Exception as e:
                msg = f"Sync encountered an error: {e}"

            def finish():
                self._is_syncing = False
                self.sync_btn.configure(text="🔄 Sync Charts", state="normal")
                self.refresh()

            self.after(0, finish)

        threading.Thread(target=worker, daemon=True).start()

    def _update_pagination(self, total: int) -> None:
        total_pages = max(1, (total + self.page_size - 1) // self.page_size)
        start = (self.current_page - 1) * self.page_size + 1 if total > 0 else 0
        end = min(self.current_page * self.page_size, total)

        self.page_info_lbl.configure(text=f"Showing {start}–{end} of {total} charts")
        self.page_num_lbl.configure(text=f"{self.current_page} / {total_pages}")

        self.first_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.prev_btn.configure(state="normal" if self.current_page > 1 else "disabled")
        self.next_btn.configure(state="normal" if self.current_page < total_pages else "disabled")

    def _go_page(self, p: int) -> None:
        total_pages = max(1, (self._total_charts + self.page_size - 1) // self.page_size)
        if 1 <= p <= total_pages:
            self.current_page = p
            self.refresh()
