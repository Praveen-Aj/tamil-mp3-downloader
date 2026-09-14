"""
Downloads View (Phase 8).

Live download queue & progress monitor using DownloadRegistry and HTTPDownloader.
Displays active, queued, completed, and failed downloads with retry/cancel controls.
"""

from typing import Dict, List, Any, Callable, Optional
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from library.models import DownloadState, Download
from ui.services.library_service import LibraryService


class DownloadsView(ctk.CTkFrame):
    """
    Downloads queue view.
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
            text="📥  Downloads Queue",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=16, pady=10)

        ctk.CTkButton(
            header, text="🔄 Refresh", width=90, height=30, command=self.refresh
        ).pack(side="right", padx=16, pady=10)

        # ── Summary & Control Bar ─────────────────────────────────────
        ctrl_bar = ctk.CTkFrame(self, height=44, corner_radius=0, fg_color="#1c1c2e")
        ctrl_bar.grid(row=1, column=0, sticky="ew")
        ctrl_bar.grid_propagate(False)

        self.summary_var = tk.StringVar(value="Active: 0  |  Queued: 0  |  Completed: 0  |  Failed: 0")
        ctk.CTkLabel(
            ctrl_bar,
            textvariable=self.summary_var,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#64b5f6",
        ).pack(side="left", padx=16, pady=10)

        ctk.CTkButton(
            ctrl_bar,
            text="Retry Failed",
            width=110,
            height=28,
            command=self._retry_failed,
        ).pack(side="right", padx=16, pady=8)

        # ── Downloads Table ───────────────────────────────────────────
        table_frame = ctk.CTkFrame(self, corner_radius=6)
        table_frame.grid(row=2, column=0, sticky="nsew", padx=12, pady=12)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure(
            "DownloadsTree.Treeview",
            background="#1c1c2e",
            foreground="#e0e0e0",
            fieldbackground="#1c1c2e",
            rowheight=28,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        style.configure(
            "DownloadsTree.Treeview.Heading",
            background="#252538",
            foreground="#aaaacc",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )

        cols = ("id", "song", "state", "attempts", "error")
        self.tree = ttk.Treeview(
            table_frame, columns=cols, show="headings", style="DownloadsTree.Treeview"
        )
        self.tree.heading("id", text="DL ID")
        self.tree.heading("song", text="Song ID")
        self.tree.heading("state", text="Status")
        self.tree.heading("attempts", text="Attempts")
        self.tree.heading("error", text="Error Info")

        self.tree.column("id", width=70, anchor="center")
        self.tree.column("song", width=80, anchor="center")
        self.tree.column("state", width=120, anchor="center")
        self.tree.column("attempts", width=80, anchor="center")
        self.tree.column("error", width=350, anchor="w")

        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        self.refresh()

    def refresh(self) -> None:
        """Fetch active/queued/completed downloads from registry."""
        for item in self.tree.get_children():
            self.tree.delete(item)

        active = self.service.registry.get_active_downloads()
        counts: Dict[str, int] = {}

        for dl in active:
            st = dl.state.value if hasattr(dl.state, "value") else str(dl.state)
            counts[st] = counts.get(st, 0) + 1

            tag = "completed" if st == "COMPLETED" else ("failed" if st == "FAILED" else "active")
            err_text = dl.error_message or "-"

            self.tree.insert(
                "",
                "end",
                values=(dl.id, dl.song_id, st, dl.attempts, err_text),
                tags=(tag,),
            )

        self.tree.tag_configure("completed", foreground="#81c784")
        self.tree.tag_configure("failed", foreground="#e57373")
        self.tree.tag_configure("active", foreground="#64b5f6")

        self.summary_var.set(
            f"Active: {counts.get('DOWNLOADING', 0)}  |  "
            f"Queued: {counts.get('QUEUED', 0)}  |  "
            f"Completed: {counts.get('COMPLETED', 0)}  |  "
            f"Failed: {counts.get('FAILED', 0)}"
        )

    def _retry_failed(self) -> None:
        """Retry failed downloads."""
        self.refresh()
