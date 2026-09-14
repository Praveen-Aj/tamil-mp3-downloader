"""
Discover View (Phase 5).

Library-centric bulk discovery interface.
Allows selection of sources and categories.
Persists discoveries into SQLite Canonical Library WITHOUT downloading.
"""

from typing import Dict, List, Any, Callable, Optional
import threading
import tkinter as tk
import customtkinter as ctk

from ui.services.library_service import LibraryService


class DiscoverView(ctk.CTkFrame):
    """
    Discovery configuration and execution view.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        on_discovery_complete: Optional[Callable[[Dict[str, Any]], None]] = None,
        **kwargs,
    ):
        super().__init__(master, corner_radius=0, **kwargs)
        self.service = service
        self.on_discovery_complete = on_discovery_complete

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#181824")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="🔍  Bulk Song Discovery",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=16, pady=10)

        # ── Configuration Form ────────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        scroll.grid_columnconfigure(0, weight=1)

        # 1. Category Selection Card
        cat_card = ctk.CTkFrame(scroll, corner_radius=6, fg_color="#1c1c2e")
        cat_card.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            cat_card,
            text="1. SELECT TARGET CATEGORY",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#90caf9",
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
                font=ctk.CTkFont(size=12),
            ).pack(anchor="w", padx=24, pady=4)

        ctk.CTkLabel(cat_card, text="", height=4).pack()

        # 2. Source Selection Card
        src_card = ctk.CTkFrame(scroll, corner_radius=6, fg_color="#1c1c2e")
        src_card.pack(fill="x", pady=6)

        ctk.CTkLabel(
            src_card,
            text="2. SELECT SOURCES TO QUERY",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ce93d8",
        ).pack(anchor="w", padx=16, pady=(12, 6))

        self.src_vars: Dict[str, ctk.BooleanVar] = {}
        sources = [
            ("MassTamilan", "masstamilan"),
            ("Tamilmp3.in / Kuttyweb", "tamilmp3"),
            ("FriendsTamilMP3", "friendstamilmp3"),
        ]

        for label, name in sources:
            var = ctk.BooleanVar(value=True)
            self.src_vars[name] = var
            ctk.CTkCheckBox(
                src_card,
                text=label,
                variable=var,
                font=ctk.CTkFont(size=12),
            ).pack(anchor="w", padx=24, pady=4)

        ctk.CTkLabel(src_card, text="", height=4).pack()

        # 3. Execution & Warning Notice Card
        notice_card = ctk.CTkFrame(scroll, corner_radius=6, fg_color="#252538")
        notice_card.pack(fill="x", pady=6)

        notice_text = (
            "ℹ Discovery Persists metadata & audio sources into SQLite Canonical Library.\n"
            "   DISCOVERY DOES NOT AUTOMATICALLY DOWNLOAD AUDIO FILES.\n"
            "   After discovery completes, you can review results, inspect duplicates, and plan downloads."
        )

        ctk.CTkLabel(
            notice_card,
            text=notice_text,
            font=ctk.CTkFont(size=11),
            justify="left",
            text_color="#a0aab8",
        ).pack(anchor="w", padx=16, pady=12)

        # 4. Trigger Button & Progress Indicator
        self.btn_run = ctk.CTkButton(
            scroll,
            text="🚀 Run Discovery (Persist to SQLite)",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            fg_color="#1f538d",
            hover_color="#2a6abf",
            command=self._start_discovery_thread,
        )
        self.btn_run.pack(fill="x", pady=(12, 6))

        self.progress = ctk.CTkProgressBar(scroll, height=10)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=4)
        self.progress.pack_forget()

        self.status_label = ctk.CTkLabel(
            scroll, text="", font=ctk.CTkFont(size=11), text_color="#aaaaaa"
        )
        self.status_label.pack(anchor="w", pady=4)

    def _start_discovery_thread(self) -> None:
        """Run discovery on background thread to keep GUI responsive."""
        selected_sources = [name for name, var in self.src_vars.items() if var.get()]
        if not selected_sources:
            self.status_label.configure(text="❌ Please select at least one source.", text_color="#ef5350")
            return

        category = self.cat_var.get()

        self.btn_run.configure(state="disabled")
        self.progress.pack(fill="x", pady=4)
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.status_label.configure(
            text="⏳ Querying sources and registering canonical songs...", text_color="#64b5f6"
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
            f"Unique Canonical Registered: {results.get('unique_registered'):,}  |  "
            f"Duplicates Collapsed: {results.get('duplicates_filtered'):,}"
        )
        self.status_label.configure(text=summary_msg, text_color="#81c784")

        if self.on_discovery_complete:
            self.on_discovery_complete(results)

    def _on_error(self, err_msg: str) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self.btn_run.configure(state="normal")
        self.status_label.configure(text=f"❌ Discovery Error: {err_msg}", text_color="#ef5350")
