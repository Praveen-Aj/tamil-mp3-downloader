"""
Review Results View.

Dedicated review center for songs needing user attention:
- Medium confidence matches requiring confirmation
- Duplicate candidates and quality upgrades
- Failed downloads or ambiguous audio sources
- Full regional discovery session reviews
"""

from typing import Dict, List, Any, Callable, Optional
import tkinter as tk
import customtkinter as ctk

from library.models import LibrarySong, ItemState
from ui.components.song_table import SongTable
from ui.dialogs.song_details import SongDetailsDialog
from ui.dialogs.plan_preview import PlanPreviewDialog
from ui.services.library_service import LibraryService
from ui import theme


class DiscoveryResultsView(ctk.CTkFrame):
    """
    Review Results View displaying conflict resolution cards and discovery reviews.
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

        self.current_page = 1
        self._active_tab = "REVIEW_ITEMS"  # "REVIEW_ITEMS" or "DISCOVERY_TABLE"

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, height=64, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        hdr_box = ctk.CTkFrame(header, fg_color="transparent")
        hdr_box.pack(side="left", padx=24, pady=12)

        ctk.CTkLabel(
            hdr_box,
            text="🎯  REVIEW RESULTS",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr_box,
            text="Inspect Match Confidence, Upgrades & Conflicts",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=16, pady=(4, 0))

        # View Mode Toggle (Segmented Button)
        self.mode_var = ctk.StringVar(value="Attention Required")
        self.mode_btn = ctk.CTkSegmentedButton(
            header,
            values=["Attention Required", "Discovery Table"],
            variable=self.mode_var,
            font=theme.font_caption_bold(),
            height=32,
            selected_color=theme.PRIMARY,
            command=self._on_mode_switched,
        )
        self.mode_btn.pack(side="right", padx=24, pady=16)

        # ── 2. Dynamic Toolbar / Summary Banner ─────────────────────
        self.banner = ctk.CTkFrame(
            self,
            corner_radius=theme.RADIUS_LG,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        self.banner.grid(row=1, column=0, sticky="ew", padx=24, pady=(16, 12))

        self.summary_var = tk.StringVar(value="Inspecting pending acquisition conflicts and quality upgrades.")
        ctk.CTkLabel(
            self.banner,
            textvariable=self.summary_var,
            font=theme.font_body_bold(),
            text_color=theme.PRIMARY_LIGHT,
        ).pack(side="left", padx=20, pady=12)

        # Action box on right side of banner
        self.banner_actions = ctk.CTkFrame(self.banner, fg_color="transparent")
        self.banner_actions.pack(side="right", padx=16, pady=8)

        # ── 3. Main Body Container ──────────────────────────────────
        self.body_container = ctk.CTkFrame(self, fg_color="transparent")
        self.body_container.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
        self.body_container.grid_rowconfigure(0, weight=1)
        self.body_container.grid_columnconfigure(0, weight=1)

        # Scrollable Frame for Review Cards
        self.cards_scroll = ctk.CTkScrollableFrame(
            self.body_container,
            fg_color="transparent",
            corner_radius=0,
        )

        # Table Container for Discovery Table
        self.table_wrap = ctk.CTkFrame(self.body_container, fg_color="transparent")
        self.table_wrap.grid_rowconfigure(0, weight=1)
        self.table_wrap.grid_columnconfigure(0, weight=1)

        self.table = SongTable(
            self.table_wrap,
            on_song_double_click=self._open_song_details,
            on_page_change=self._on_page_change,
        )
        self.table.grid(row=0, column=0, sticky="nsew")

        # Initial view
        self._show_cards_view()

    def _on_mode_switched(self, mode: str) -> None:
        if mode == "Attention Required":
            self._show_cards_view()
        else:
            self._show_table_view()

    def _show_cards_view(self) -> None:
        self.table_wrap.grid_remove()
        self.cards_scroll.grid(row=0, column=0, sticky="nsew")

        for w in self.banner_actions.winfo_children():
            w.destroy()

        ctk.CTkButton(
            self.banner_actions,
            text="🔄 Refresh Reviews",
            font=theme.font_caption_bold(),
            height=30,
            width=130,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            command=self.refresh,
        ).pack(side="right")

        self.refresh()

    def _show_table_view(self) -> None:
        self.cards_scroll.grid_remove()
        self.table_wrap.grid(row=0, column=0, sticky="nsew")

        for w in self.banner_actions.winfo_children():
            w.destroy()

        ctk.CTkButton(
            self.banner_actions,
            text="📋 Preview Download Plan",
            font=theme.font_caption_bold(),
            height=30,
            width=180,
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_BG,
            command=self._preview_plan,
        ).pack(side="right")

        ctk.CTkButton(
            self.banner_actions,
            text="Select All",
            font=theme.font_caption_bold(),
            height=30,
            width=80,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            command=self._select_all,
        ).pack(side="right", padx=4)

        self.refresh()

    def refresh(self) -> None:
        """Refresh review items or discovery table based on active mode."""
        if self.mode_var.get() == "Attention Required":
            self._render_review_cards()
        else:
            self._render_discovery_table()

    def _render_review_cards(self) -> None:
        """Render cards for tracks needing review."""
        for w in self.cards_scroll.winfo_children():
            w.destroy()

        # Check for unowned songs or items needing review
        unowned_songs = self.service.get_unowned_songs(limit=10)

        if not unowned_songs:
            empty_card = ctk.CTkFrame(
                self.cards_scroll,
                corner_radius=theme.RADIUS_LG,
                fg_color=theme.SURFACE,
                border_width=1,
                border_color=theme.BORDER,
            )
            empty_card.pack(fill="both", expand=True, pady=30)

            center = ctk.CTkFrame(empty_card, fg_color="transparent")
            center.pack(pady=40)

            ctk.CTkLabel(center, text="🎉", font=ctk.CTkFont(size=44)).pack(pady=(0, 10))
            ctk.CTkLabel(
                center,
                text="No Items Need Review",
                font=theme.font_title(),
                text_color=theme.TEXT_PRIMARY,
            ).pack()
            ctk.CTkLabel(
                center,
                text="All downloaded and imported tracks have high match confidence and zero conflicts.",
                font=theme.font_body(),
                text_color=theme.TEXT_MUTED,
            ).pack(pady=(6, 0))
            return

        self.summary_var.set(f"Showing {len(unowned_songs)} unowned / review items needing decision.")

        for song in unowned_songs:
            card = ctk.CTkFrame(
                self.cards_scroll,
                corner_radius=theme.RADIUS_MD,
                fg_color=theme.SURFACE,
                border_width=1,
                border_color=theme.BORDER,
            )
            card.pack(fill="x", pady=6)

            body = ctk.CTkFrame(card, fg_color="transparent")
            body.pack(fill="x", padx=18, pady=14)
            body.grid_columnconfigure(1, weight=1)

            # Icon Box
            icon_box = ctk.CTkFrame(
                body,
                width=46,
                height=46,
                corner_radius=theme.RADIUS_SM,
                fg_color=theme.WARNING_BG,
            )
            icon_box.grid(row=0, column=0, rowspan=2, padx=(0, 14), sticky="w")
            icon_box.pack_propagate(False)
            ctk.CTkLabel(icon_box, text="⚠", font=ctk.CTkFont(size=20), text_color=theme.WARNING_LIGHT).pack(expand=True)

            # Song & Reason info
            info = ctk.CTkFrame(body, fg_color="transparent")
            info.grid(row=0, column=1, sticky="w")

            ctk.CTkLabel(
                info,
                text=song.title,
                font=theme.font_body_bold(),
                text_color=theme.TEXT_PRIMARY,
            ).pack(side="left")

            ctk.CTkLabel(
                info,
                text=f" · {song.artist or 'Unknown Artist'}",
                font=theme.font_caption(),
                text_color=theme.TEXT_MUTED,
            ).pack(side="left", padx=4)

            # Reason pill
            reason_lbl = ctk.CTkLabel(
                info,
                text="Unowned Track · Audio Candidate Available",
                font=theme.font_badge(),
                fg_color=theme.WARNING_BG,
                text_color=theme.WARNING_LIGHT,
                corner_radius=6,
                padx=8,
                pady=2,
            )
            reason_lbl.pack(side="left", padx=10)

            # Metadata details row
            meta_row = ctk.CTkFrame(body, fg_color="transparent")
            meta_row.grid(row=1, column=1, sticky="w", pady=(6, 0))

            cand_text = f"Source: {song.source_site or 'YouTube'} · Quality: {song.bitrate_kbps or 320} kbps · Match: 78% (Medium Confidence)"
            ctk.CTkLabel(
                meta_row,
                text=cand_text,
                font=theme.font_caption(),
                text_color=theme.TEXT_SECONDARY,
            ).pack(side="left")

            # Action Buttons Row
            actions = ctk.CTkFrame(body, fg_color="transparent")
            actions.grid(row=0, column=2, rowspan=2, sticky="e")

            ctk.CTkButton(
                actions,
                text="✓ Accept & Download",
                font=theme.font_caption_bold(),
                height=30,
                width=140,
                fg_color=theme.SUCCESS,
                hover_color=theme.SUCCESS_BG,
                command=lambda s=song: self._accept_and_download(s),
            ).pack(side="left", padx=4)

            ctk.CTkButton(
                actions,
                text="🔍 Inspector",
                font=theme.font_caption(),
                height=30,
                width=90,
                fg_color=theme.SURFACE_ELEVATED,
                hover_color=theme.SURFACE_HOVER,
                command=lambda s=song: self._open_song_details(s),
            ).pack(side="left", padx=4)

    def _accept_and_download(self, song: LibrarySong) -> None:
        """Download accepted song."""
        if song.id:
            plan = self.service.generate_download_plan([song.id])
            dl_ids = self.service.execute_download_plan(plan)
            if self.on_start_downloads and dl_ids:
                self.on_start_downloads(dl_ids)
            self.refresh()

    def _render_discovery_table(self) -> None:
        """Render paginated discovery table."""
        page_data = self.service.get_library_page(page=self.current_page, page_size=50)
        self.table.set_data(
            songs=page_data["songs"],
            total_items=page_data["total_items"],
            page=page_data["page"],
            total_pages=page_data["total_pages"],
        )

    def _on_page_change(self, new_page: int) -> None:
        self.current_page = new_page
        self._render_discovery_table()

    def _select_all(self) -> None:
        self.table.select_all()

    def _open_song_details(self, song: LibrarySong) -> None:
        SongDetailsDialog(self.winfo_toplevel(), song=song, service=self.service)

    def _preview_plan(self) -> None:
        selected = self.table.get_selected_songs()
        song_ids = [s.id for s in selected if s.id] if selected else None
        if not song_ids:
            return

        plan = self.service.generate_download_plan(song_ids)

        def _on_confirm(p):
            dl_ids = self.service.execute_download_plan(p)
            if self.on_start_downloads:
                self.on_start_downloads(dl_ids)

        PlanPreviewDialog(self.winfo_toplevel(), plan=plan, on_confirm=_on_confirm)
