"""
Sources View (Phase 10).

Displays source health, active/fallback domains, reliability scores, and runtime status.
Allows running live health checks across registered sources.
"""

from typing import Dict, List, Any, Callable, Optional
import threading
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from ui.services.library_service import LibraryService


class SourcesView(ctk.CTkFrame):
    """
    Source Health Matrix View.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        **kwargs,
    ):
        super().__init__(master, corner_radius=0, **kwargs)
        self.service = service

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#181824")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="🌐  Source Health & Domain Registry",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=16, pady=10)

        self.btn_check = ctk.CTkButton(
            header, text="⚡ Run Health Check", width=140, height=30, command=self._run_health_check
        )
        self.btn_check.pack(side="right", padx=16, pady=10)

        # ── Status Summary ────────────────────────────────────────────
        summary_bar = ctk.CTkFrame(self, height=40, corner_radius=0, fg_color="#1c1c2e")
        summary_bar.grid(row=1, column=0, sticky="ew")
        summary_bar.grid_propagate(False)

        self.summary_var = tk.StringVar(value="Sources: Checking status...")
        ctk.CTkLabel(
            summary_bar,
            textvariable=self.summary_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#4caf50",
        ).pack(side="left", padx=16, pady=8)

        # ── Sources Table ─────────────────────────────────────────────
        table_frame = ctk.CTkFrame(self, corner_radius=6)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=12)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure(
            "SourcesTree.Treeview",
            background="#1c1c2e",
            foreground="#e0e0e0",
            fieldbackground="#1c1c2e",
            rowheight=32,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        style.configure(
            "SourcesTree.Treeview.Heading",
            background="#252538",
            foreground="#aaaacc",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )

        cols = ("name", "status", "enabled", "domain", "score", "last_error")
        self.tree = ttk.Treeview(
            table_frame, columns=cols, show="headings", style="SourcesTree.Treeview"
        )
        self.tree.heading("name", text="Source Name")
        self.tree.heading("status", text="Health Status")
        self.tree.heading("enabled", text="Enabled")
        self.tree.heading("domain", text="Active Domain")
        self.tree.heading("score", text="Reliability Score")
        self.tree.heading("last_error", text="Last Error Info")

        self.tree.column("name", width=140, anchor="w")
        self.tree.column("status", width=110, anchor="center")
        self.tree.column("enabled", width=80, anchor="center")
        self.tree.column("domain", width=220, anchor="w")
        self.tree.column("score", width=110, anchor="center")
        self.tree.column("last_error", width=280, anchor="w")

        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        self.refresh()

    def refresh(self) -> None:
        """Populate treeview with registered source status."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        sources = self.service.source_registry.get_all_sources()
        healthy_cnt = 0

        for s in sources:
            st = s.runtime.health.value if hasattr(s.runtime.health, "value") else str(s.runtime.health)
            if s.is_usable:
                healthy_cnt += 1

            enabled_str = "Yes" if s.config.enabled else "No (Disabled)"
            domain_str = s.active_domain or "-"
            score_str = f"{s.runtime.reliability_score:.2f}"
            err_str = s.runtime.last_error or "-"

            tag = "healthy" if s.is_usable else ("disabled" if not s.config.enabled else "unavail")

            self.tree.insert(
                "",
                "end",
                values=(s.config.display_name, st, enabled_str, domain_str, score_str, err_str),
                tags=(tag,),
            )

        self.tree.tag_configure("healthy", foreground="#81c784")
        self.tree.tag_configure("disabled", foreground="#888888")
        self.tree.tag_configure("unavail", foreground="#e57373")

        self.summary_var.set(f"Usable Core Sources: {healthy_cnt} / {len(sources)}")

    def _run_health_check(self) -> None:
        """Run network connection tests for all sources on background thread."""
        self.btn_check.configure(state="disabled")
        self.summary_var.set("Running connection tests across sources...")

        def _worker():
            for name in ["masstamilan", "tamilmp3", "friendstamilmp3"]:
                src = self.service.source_registry.get_source(name)
                if src and src.scraper:
                    try:
                        ok = src.scraper.test_connection()
                        if ok:
                            self.service.source_registry.record_success(name)
                        else:
                            self.service.source_registry.record_failure(name, "Connection test returned False")
                    except Exception as e:
                        self.service.source_registry.record_failure(name, str(e))
            self.after(0, self._on_health_check_complete)

        threading.Thread(target=_worker, daemon=True).start()

    def _on_health_check_complete(self) -> None:
        self.btn_check.configure(state="normal")
        self.refresh()
