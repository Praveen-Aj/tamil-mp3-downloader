"""
Redesigned Modern Dashboard View.

Consumer-focused desktop overview featuring:
- Compact Hero banner with primary CTA ("Download your music") and quick actions
- 6 Key Performance Metric cards with clear consumer terminology
- Compact horizontal single-line Source Status bar
- Recently Added Music cards with artwork and bitrate badges
- Recent URL/Playlist imports table with progress and actions
"""

from typing import Dict, Any, Callable, List
import tkinter as tk
import customtkinter as ctk

from library.models import ImportJob, JobStatus, LibrarySong
from ui.services.library_service import LibraryService
from ui import theme


class DashboardView(ctk.CTkFrame):
    """
    Polished desktop music dashboard with first-viewport optimization.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_navigate: Callable[[str], None],
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.service = service
        self.on_navigate = on_navigate

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        title_frame = ctk.CTkFrame(header, fg_color="transparent")
        title_frame.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            title_frame,
            text="📊  DASHBOARD",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        # Action buttons in header
        btn_box = ctk.CTkFrame(header, fg_color="transparent")
        btn_box.pack(side="right", padx=16, pady=10)

        ctk.CTkButton(
            btn_box,
            text="🔄 Refresh",
            width=85,
            height=32,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            font=theme.font_body(),
            corner_radius=theme.RADIUS_MD,
            command=self.refresh,
        ).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            btn_box,
            text="⚡ + Add Music",
            font=theme.font_body_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.TEXT_PRIMARY,
            width=120,
            height=32,
            corner_radius=theme.RADIUS_MD,
            command=lambda: self.on_navigate("add_music"),
        ).pack(side="right")

        # ── 2. Main Scrollable Container ────────────────────────────
        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=12)
        self.scroll.grid_columnconfigure(0, weight=1)

        # ── 3. Compact Hero Acquisition Banner ──────────────────────
        hero = ctk.CTkFrame(
            self.scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        hero.pack(fill="x", pady=(0, 12))
        hero.grid_columnconfigure(0, weight=1)

        hero_body = ctk.CTkFrame(hero, fg_color="transparent")
        hero_body.pack(fill="x", padx=18, pady=12)

        hero_top = ctk.CTkFrame(hero_body, fg_color="transparent")
        hero_top.pack(fill="x")

        # Text side
        text_box = ctk.CTkFrame(hero_top, fg_color="transparent")
        text_box.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            text_box,
            text="🎵  Download Your Music",
            font=theme.font_title(),
            text_color=theme.TEXT_PRIMARY,
            anchor="w",
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_box,
            text="Paste a YouTube or Spotify playlist/track URL to detect, match, and organize high-quality 320 kbps MP3s.",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
            anchor="w",
        ).pack(anchor="w", pady=(2, 8))

        # Action Buttons Row
        action_row = ctk.CTkFrame(text_box, fg_color="transparent")
        action_row.pack(anchor="w")

        ctk.CTkButton(
            action_row,
            text="⚡ + Add Music via URL",
            font=theme.font_caption_bold(),
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            text_color=theme.TEXT_PRIMARY,
            height=32,
            width=160,
            corner_radius=theme.RADIUS_MD,
            command=lambda: self.on_navigate("add_music"),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            action_row,
            text="📚 Music Library",
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            height=32,
            width=120,
            corner_radius=theme.RADIUS_MD,
            command=lambda: self.on_navigate("library"),
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            action_row,
            text="🔍 Discover Regional",
            font=theme.font_caption_bold(),
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            height=32,
            width=140,
            corner_radius=theme.RADIUS_MD,
            command=lambda: self.on_navigate("discover"),
        ).pack(side="left")

        # ── 4. 6 Consumer KPI Metric Cards ──────────────────────────
        self._card_vars: Dict[str, tk.StringVar] = {}
        self._build_kpi_cards()

        # ── 5. Sleek Compact Horizontal Source Status Bar ───────────
        self._build_compact_sources_bar()

        # ── 6. Recently Added Music Section ─────────────────────────
        self.snapshot_card = ctk.CTkFrame(
            self.scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        self.snapshot_card.pack(fill="x", pady=(0, 12))
        self._build_snapshot_panel()

        # ── 7. Recent Imports Section ───────────────────────────────
        self.jobs_card = ctk.CTkFrame(
            self.scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        self.jobs_card.pack(fill="x", pady=(0, 10))
        self._build_recent_imports_panel()

        # Load data
        self.refresh()

    def _build_kpi_cards(self) -> None:
        """Create 6 distinct KPI metric cards with clear consumer terminology."""
        grid_frame = ctk.CTkFrame(self.scroll, fg_color="transparent")
        grid_frame.pack(fill="x", pady=(0, 12))
        for i in range(6):
            grid_frame.grid_columnconfigure(i, weight=1)

        cards = [
            ("total_songs", "📚 Total Songs", "0", "In Music Library", theme.PRIMARY),
            ("owned_songs", "✓ Downloaded", "0", "Ready to play", theme.SUCCESS),
            ("ready_downloads", "↓ Ready to Download", "0", "Available to get", theme.INFO),
            ("active_downloads", "⏳ Active Downloads", "0", "In progress", theme.ACCENT_CYAN),
            ("failed_downloads", "⚠ Needs Attention", "0", "Review or retry", theme.WARNING),
            ("storage_used", "💾 Storage Used", "0 MB", "Audio on disk", theme.TEXT_SECONDARY),
        ]

        for idx, (key, title, default_val, subtitle, accent_color) in enumerate(cards):
            card = ctk.CTkFrame(
                grid_frame,
                corner_radius=theme.RADIUS_MD,
                fg_color=theme.SURFACE,
                border_width=1,
                border_color=theme.BORDER,
            )
            card.grid(row=0, column=idx, padx=3, sticky="nsew")

            content = ctk.CTkFrame(card, fg_color="transparent")
            content.pack(fill="both", padx=10, pady=10)

            # Top label
            ctk.CTkLabel(
                content,
                text=title,
                font=theme.font_caption_bold(),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w")

            # Value
            var = tk.StringVar(value=default_val)
            self._card_vars[key] = var
            val_lbl = ctk.CTkLabel(
                content,
                textvariable=var,
                font=theme.font_title(),
                text_color=accent_color,
                anchor="w",
            )
            val_lbl.pack(anchor="w", pady=(2, 1))

            # Context
            ctk.CTkLabel(
                content,
                text=subtitle,
                font=ctk.CTkFont(size=9),
                text_color=theme.TEXT_DIM,
                anchor="w",
            ).pack(anchor="w")

    def _build_compact_sources_bar(self) -> None:
        """Construct compact single-line horizontal provider status row."""
        bar = ctk.CTkFrame(
            self.scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
            height=38,
        )
        bar.pack(fill="x", pady=(0, 12))
        bar.pack_propagate(False)

        inner = ctk.CTkFrame(bar, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=14)

        ctk.CTkLabel(
            inner,
            text="Sources:",
            font=theme.font_caption_bold(),
            text_color=theme.TEXT_SECONDARY,
        ).pack(side="left", padx=(0, 12))

        self.sources_box = ctk.CTkFrame(inner, fg_color="transparent")
        self.sources_box.pack(side="left", fill="both", expand=True)

    def _render_source_pills(self, pills: List[Dict[str, Any]]) -> None:
        for w in self.sources_box.winfo_children():
            w.destroy()

        for p in pills:
            pill_frame = ctk.CTkFrame(self.sources_box, fg_color="transparent")
            pill_frame.pack(side="left", padx=10)

            dot = ctk.CTkLabel(
                pill_frame,
                text="●",
                font=ctk.CTkFont(size=11),
                text_color=p.get("color", theme.SUCCESS),
            )
            dot.pack(side="left", padx=(0, 4))

            name_lbl = ctk.CTkLabel(
                pill_frame,
                text=f"{p['name']} ({p['status']})",
                font=theme.font_caption(),
                text_color=theme.TEXT_PRIMARY,
            )
            name_lbl.pack(side="left")

    def _build_snapshot_panel(self) -> None:
        """Construct Library Snapshot / Recently Added Music section."""
        hdr = ctk.CTkFrame(self.snapshot_card, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkLabel(
            hdr,
            text="🎧  Recently Added Music",
            font=theme.font_subtitle(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkButton(
            hdr,
            text="Open Music Library",
            font=theme.font_caption_bold(),
            width=120,
            height=24,
            fg_color="transparent",
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.PRIMARY_LIGHT,
            command=lambda: self.on_navigate("library"),
        ).pack(side="right")

        self.snapshot_container = ctk.CTkFrame(self.snapshot_card, fg_color="transparent")
        self.snapshot_container.pack(fill="x", padx=16, pady=(0, 12))

    def _build_recent_imports_panel(self) -> None:
        """Construct Recent Imports section."""
        hdr = ctk.CTkFrame(self.jobs_card, fg_color="transparent")
        hdr.pack(fill="x", padx=16, pady=(12, 8))

        ctk.CTkLabel(
            hdr,
            text="📥  Recent URL & Playlist Imports",
            font=theme.font_subtitle(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkButton(
            hdr,
            text="View All Downloads",
            font=theme.font_caption_bold(),
            width=120,
            height=24,
            fg_color="transparent",
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.PRIMARY_LIGHT,
            command=lambda: self.on_navigate("downloads"),
        ).pack(side="right")

        self.jobs_list = ctk.CTkFrame(self.jobs_card, fg_color="transparent")
        self.jobs_list.pack(fill="x", padx=16, pady=(0, 12))

    def refresh(self) -> None:
        """Fetch fresh metrics from service and render list items."""
        stats = self.service.get_dashboard_stats()

        total = stats.get("total_songs", 0)
        owned = stats.get("owned_songs", 0)
        ready = stats.get("ready_downloads", 0)
        active = stats.get("active_downloads", 0)
        failed = stats.get("failed_downloads", 0)
        storage_mb = stats.get("storage_mb", owned * 8)

        self._card_vars["total_songs"].set(f"{total:,}")
        self._card_vars["owned_songs"].set(f"{owned:,}")
        self._card_vars["ready_downloads"].set(f"{ready:,}")
        self._card_vars["active_downloads"].set(f"{active:,}")
        self._card_vars["failed_downloads"].set(f"{failed:,}")
        if storage_mb >= 1024:
            self._card_vars["storage_used"].set(f"{storage_mb/1024:.1f} GB")
        else:
            self._card_vars["storage_used"].set(f"{storage_mb:,} MB")

        pills = stats.get("source_pills", [
            {"name": "YouTube", "status": "Active", "color": "#10b981"},
            {"name": "Spotify", "status": "Ready", "color": "#10b981"},
            {"name": "Direct Audio", "status": "Active", "color": "#10b981"},
            {"name": "Regional Tamil", "status": "Online", "color": "#10b981"},
        ])
        self._render_source_pills(pills)
        self._render_recent_jobs()
        self._render_library_snapshot()

    def _render_recent_jobs(self) -> None:
        """Render recent import jobs or empty state."""
        for w in self.jobs_list.winfo_children():
            w.destroy()

        jobs = self.service.get_recent_import_jobs(limit=3)
        if not jobs:
            empty = ctk.CTkFrame(self.jobs_list, fg_color="transparent")
            empty.pack(fill="x", pady=8)
            ctk.CTkLabel(
                empty,
                text="✨  No recent imports yet · Paste a music or playlist URL above to get started",
                font=theme.font_caption(),
                text_color=theme.TEXT_DIM,
            ).pack()
            return

        for job in jobs:
            card = ctk.CTkFrame(
                self.jobs_list,
                fg_color=theme.SURFACE_ELEVATED,
                corner_radius=theme.RADIUS_SM,
                border_width=1,
                border_color=theme.BORDER,
            )
            card.pack(fill="x", pady=3)

            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=8)

            # Platform icon
            icon = "🟢" if "spotify" in job.url.lower() else "🔴" if "youtu" in job.url.lower() else "🔗"
            ctk.CTkLabel(row, text=icon, font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 8))

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True)

            ctk.CTkLabel(
                info,
                text=job.title or "Untitled Import",
                font=theme.font_body_bold(),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
            ).pack(anchor="w")

            meta_txt = f"{job.track_count} tracks · {job.platform.capitalize() if job.platform else 'Web'}"
            ctk.CTkLabel(
                info,
                text=meta_txt,
                font=theme.font_caption(),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w")

            # Progress / Status pill
            status_text = "Completed" if job.status == JobStatus.COMPLETED else "Pending"
            color = theme.SUCCESS if job.status == JobStatus.COMPLETED else theme.INFO
            badge = ctk.CTkLabel(
                row,
                text=status_text,
                font=theme.font_badge(),
                fg_color=color,
                text_color=theme.TEXT_PRIMARY,
                corner_radius=6,
                padx=8,
                pady=2,
            )
            badge.pack(side="right", padx=6)

    def _render_library_snapshot(self) -> None:
        """Render recent library tracks."""
        for w in self.snapshot_container.winfo_children():
            w.destroy()

        songs = self.service.get_all_songs(limit=4)
        if not songs:
            empty = ctk.CTkFrame(self.snapshot_container, fg_color="transparent")
            empty.pack(fill="x", pady=10)
            ctk.CTkLabel(
                empty,
                text="Music library is currently empty · Add your first tracks above",
                font=theme.font_caption(),
                text_color=theme.TEXT_DIM,
            ).pack()
            return

        row_frame = ctk.CTkFrame(self.snapshot_container, fg_color="transparent")
        row_frame.pack(fill="x")
        for i in range(len(songs)):
            row_frame.grid_columnconfigure(i, weight=1)

        for idx, song in enumerate(songs):
            item = ctk.CTkFrame(
                row_frame,
                fg_color=theme.SURFACE_ELEVATED,
                corner_radius=theme.RADIUS_MD,
                border_width=1,
                border_color=theme.BORDER,
            )
            item.grid(row=0, column=idx, padx=3, sticky="nsew")

            content = ctk.CTkFrame(item, fg_color="transparent")
            content.pack(fill="both", padx=10, pady=10)

            # Album Art Placeholder Badge
            art = ctk.CTkFrame(
                content,
                width=36,
                height=36,
                corner_radius=theme.RADIUS_SM,
                fg_color=theme.SURFACE_ACTIVE,
            )
            art.pack(anchor="w")
            art.pack_propagate(False)
            ctk.CTkLabel(art, text="🎵", font=ctk.CTkFont(size=16)).pack(expand=True)

            ctk.CTkLabel(
                content,
                text=song.title,
                font=theme.font_body_bold(),
                text_color=theme.TEXT_PRIMARY,
                anchor="w",
            ).pack(anchor="w", pady=(6, 2))

            ctk.CTkLabel(
                content,
                text=song.artist or "Unknown Artist",
                font=theme.font_caption(),
                text_color=theme.TEXT_MUTED,
                anchor="w",
            ).pack(anchor="w")

            # Bitrate pill
            bitrate_text = f"{song.bitrate_kbps} kbps" if song.bitrate_kbps else "320 kbps"
            ctk.CTkLabel(
                content,
                text=bitrate_text,
                font=theme.font_badge(),
                text_color=theme.ACCENT_CYAN,
                anchor="w",
            ).pack(anchor="w", pady=(3, 0))
