"""
Discover View (Phase 5).

Library-centric bulk discovery interface.
Allows selection of regional sources and categories.
Persists discoveries into SQLite Music Library WITHOUT downloading.
Features dynamic Discovery Preview card to utilize view space efficiently.
"""

from typing import Dict, List, Any, Callable, Optional
import threading
import tkinter as tk
import customtkinter as ctk

from ui.services.library_service import LibraryService
from ui import theme


class DiscoverView(ctk.CTkFrame):
    """
    Discovery configuration and execution view with live Discovery Preview card.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_discovery_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        **kwargs,
    ):
        super().__init__(master, fg_color="transparent", corner_radius=0, **kwargs)
        self.service = service
        self.on_discovery_complete = on_discovery_complete

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Top Header ───────────────────────────────────────────
        header = ctk.CTkFrame(self, height=56, corner_radius=0, fg_color=theme.BG_HEADER)
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        hdr_box = ctk.CTkFrame(header, fg_color="transparent")
        hdr_box.pack(side="left", padx=20, pady=10)

        ctk.CTkLabel(
            hdr_box,
            text="🔍  DISCOVER REGIONAL",
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            hdr_box,
            text="Bulk Song & Album Catalog Indexing",
            font=theme.font_caption(),
            text_color=theme.TEXT_MUTED,
        ).pack(side="left", padx=14, pady=(2, 0))

        # ── 2. Main Scrollable Container ────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew", padx=20, pady=12)
        scroll.grid_columnconfigure(0, weight=1)

        # 1. Category Selection Card
        cat_card = ctk.CTkFrame(
            scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        cat_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            cat_card,
            text="1. SELECT TARGET CATEGORY",
            font=theme.font_caption_bold(),
            text_color=theme.PRIMARY_LIGHT,
        ).pack(anchor="w", padx=16, pady=(12, 6))

        self.cat_var = ctk.StringVar(value="latest")
        categories = [
            ("Latest Releases (2026)", "latest"),
            ("Top 2026 Hits", "2026"),
            ("Top 2025 Hits", "2025"),
            ("Star Actors Collection", "stars"),
            ("Singers Special", "singers"),
            ("Music Directors (MDs)", "music-directors"),
        ]

        for label, val in categories:
            ctk.CTkRadioButton(
                cat_card,
                text=label,
                value=val,
                variable=self.cat_var,
                font=theme.font_body(),
                text_color=theme.TEXT_PRIMARY,
                fg_color=theme.PRIMARY,
                command=self._update_preview,
            ).pack(anchor="w", padx=20, pady=3)

        ctk.CTkLabel(cat_card, text="", height=4).pack()

        # 2. Source Selection Card
        src_card = ctk.CTkFrame(
            scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        src_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            src_card,
            text="2. SELECT REGIONAL SOURCES",
            font=theme.font_caption_bold(),
            text_color=theme.ACCENT_PURPLE,
        ).pack(anchor="w", padx=16, pady=(12, 6))

        self.src_vars: Dict[str, ctk.BooleanVar] = {}
        sources = [
            ("MassTamilan (320 kbps & 128 kbps)", "masstamilan"),
            ("Tamilmp3.in / Kuttyweb (Original Masters)", "tamilmp3"),
            ("FriendsTamilMP3 (Classic & 128 kbps Archive)", "friendstamilmp3"),
        ]

        for label, name in sources:
            var = ctk.BooleanVar(value=True)
            self.src_vars[name] = var
            ctk.CTkCheckBox(
                src_card,
                text=label,
                variable=var,
                font=theme.font_body(),
                text_color=theme.TEXT_PRIMARY,
                fg_color=theme.PRIMARY,
                command=self._update_preview,
            ).pack(anchor="w", padx=20, pady=3)

        ctk.CTkLabel(src_card, text="", height=4).pack()

        # 3. Dynamic Discovery Preview Card (Fills empty area with useful scope)
        self.preview_card = ctk.CTkFrame(
            scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE_ELEVATED,
            border_width=1,
            border_color=theme.BORDER,
        )
        self.preview_card.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            self.preview_card,
            text="🎯  DISCOVERY PREVIEW & EXECUTION",
            font=theme.font_caption_bold(),
            text_color=theme.SUCCESS_LIGHT,
        ).pack(anchor="w", padx=16, pady=(12, 6))

        self.preview_text_var = tk.StringVar()
        self._update_preview()

        ctk.CTkLabel(
            self.preview_card,
            textvariable=self.preview_text_var,
            font=theme.font_caption(),
            text_color=theme.TEXT_SECONDARY,
            justify="left",
            anchor="w",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # 4. Trigger Button & Progress Indicator
        self.btn_run = ctk.CTkButton(
            scroll,
            text="🚀 Run Discovery (Index into Music Library)",
            font=theme.font_body_bold(),
            height=38,
            fg_color=theme.PRIMARY,
            hover_color=theme.PRIMARY_HOVER,
            corner_radius=theme.RADIUS_MD,
            command=self._start_discovery_thread,
        )
        self.btn_run.pack(fill="x", pady=(4, 6))

        self.progress = ctk.CTkProgressBar(scroll, height=8, progress_color=theme.PRIMARY)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=4)
        self.progress.pack_forget()

        self.status_label = ctk.CTkLabel(
            scroll, text="", font=theme.font_caption(), text_color=theme.TEXT_MUTED
        )
        self.status_label.pack(anchor="w", pady=4)

    def _update_preview(self) -> None:
        selected_sources = [name for name, var in self.src_vars.items() if var.get()]
        cat = self.cat_var.get()
        src_names = ", ".join(s.capitalize() for s in selected_sources) or "None selected"

        preview = (
            f"Category:  {cat.upper()} Releases\n"
            f"Sources:   {src_names}\n"
            f"Behavior:  Discovers and indexes song metadata into SQLite Music Library without downloading.\n"
            f"Next Step: Review match confidence in Review Results or preview download plans."
        )
        self.preview_text_var.set(preview)

    def _start_discovery_thread(self) -> None:
        """Run discovery on background thread to keep GUI responsive."""
        selected_sources = [name for name, var in self.src_vars.items() if var.get()]
        if not selected_sources:
            self.status_label.configure(text="❌ Please select at least one source.", text_color=theme.ERROR)
            return

        category = self.cat_var.get()

        self.btn_run.configure(state="disabled")
        self.progress.pack(fill="x", pady=4)
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status_label.configure(
            text="⏳ Querying regional archives and registering tracks into your Music Library...", text_color=theme.INFO
        )

        def _worker():
            try:
                res = self.service.run_discovery(category=category, source_names=selected_sources)
                self.after(0, lambda: self._on_success(res))
            except Exception as e:
                self.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_success(self, results: Dict[str, Any]) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self.btn_run.configure(state="normal")

        summary_msg = (
            f"✅ Discovery Complete!\n"
            f"Raw Discoveries: {results.get('raw_discovered'):,}  |  "
            f"Unique Registered: {results.get('unique_registered'):,}  |  "
            f"Duplicates Filtered: {results.get('duplicates_filtered'):,}"
        )
        self.status_label.configure(text=summary_msg, text_color=theme.SUCCESS_LIGHT)

        if self.on_discovery_complete:
            self.on_discovery_complete(results)

    def _on_error(self, err_msg: str) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self.btn_run.configure(state="normal")
        self.status_label.configure(text=f"❌ Discovery Error: {err_msg}", text_color=theme.ERROR)
