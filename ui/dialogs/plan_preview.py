"""
Download Plan Preview dialog.

Presents explicit download breakdown before invoking the downloader.
Displays metrics, source selections, quality upgrades vs new downloads, and unresolvable items.
Buttons: [Start Download], [Review Details], [Cancel].
"""

from typing import Any, Callable, Optional
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from library.planner import DownloadPlan


class PlanPreviewDialog(ctk.CTkToplevel):
    """
    Explicit Download Plan Preview Modal Dialog.
    """

    def __init__(
        self,
        master: Any,
        plan: DownloadPlan,
        on_confirm: Callable[[], None],
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.title("📋 Download Plan Preview")
        self.geometry("700x580")
        self.minsize(600, 480)
        self.grab_set()

        self.plan = plan
        self.on_confirm = on_confirm

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Summary Header Card ────────────────────────────────────
        header_frame = ctk.CTkFrame(self, corner_radius=6, fg_color="#1c1c2e")
        header_frame.grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))
        header_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="DOWNLOAD PLAN BREAKDOWN",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#90caf9",
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(10, 6), sticky="w")

        selected_cnt = len(plan.planned_songs)
        owned_cnt = len(plan.owned_songs)
        new_cnt = len(plan.new_songs)
        unavail_cnt = len(plan.unresolvable)
        
        # Check quality upgrades count
        upgrades_cnt = sum(
            1 for ps in plan.new_songs
            if ps.song.state == "OWNED" or (ps.song.quality_kbps and ps.target_quality and ps.target_quality > ps.song.quality_kbps)
        )
        actual_dl_cnt = new_cnt

        summary_text = (
            f"Selected Songs:      {selected_cnt:>5}\n"
            f"Already Owned:       {owned_cnt:>5}\n"
            f"New Downloads:       {new_cnt - upgrades_cnt:>5}\n"
            f"Quality Upgrades:    {upgrades_cnt:>5}\n"
            f"Unavailable:         {unavail_cnt:>5}\n"
            f"-------------------------------\n"
            f"Actual Downloads:    {actual_dl_cnt:>5}"
        )

        ctk.CTkLabel(
            header_frame,
            text=summary_text,
            font=ctk.CTkFont(family="Consolas", size=12),
            justify="left",
            text_color="#e0e0e0",
        ).grid(row=1, column=0, padx=14, pady=(0, 10), sticky="w")

        # ── 2. Detailed Table Preview ──────────────────────────────────
        table_frame = ctk.CTkFrame(self, corner_radius=6)
        table_frame.grid(row=1, column=0, sticky="nsew", padx=14, pady=6)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure(
            "PlanTree.Treeview",
            background="#1c1c2e",
            foreground="#e0e0e0",
            fieldbackground="#1c1c2e",
            rowheight=26,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        style.configure(
            "PlanTree.Treeview.Heading",
            background="#252538",
            foreground="#aaaacc",
            font=("Segoe UI", 9, "bold"),
            relief="flat",
        )

        cols = ("title", "artist", "type", "source", "quality")
        self.tree = ttk.Treeview(
            table_frame, columns=cols, show="headings", style="PlanTree.Treeview"
        )
        self.tree.heading("title", text="Song Title")
        self.tree.heading("artist", text="Artist")
        self.tree.heading("type", text="Action")
        self.tree.heading("source", text="Source")
        self.tree.heading("quality", text="Target Quality")

        self.tree.column("title", width=200, anchor="w")
        self.tree.column("artist", width=140, anchor="w")
        self.tree.column("type", width=110, anchor="center")
        self.tree.column("source", width=110, anchor="w")
        self.tree.column("quality", width=90, anchor="center")

        self.tree.grid(row=0, column=0, sticky="nsew")

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=vsb.set)

        # Populate rows
        for ps in plan.new_songs:
            is_upgrade = ps.song.quality_kbps and ps.target_quality and ps.target_quality > ps.song.quality_kbps
            action_str = "Upgrade" if is_upgrade else "New Download"
            src_name = ps.primary.source_name if ps.primary else "-"
            q_str = f"{ps.target_quality} kbps" if ps.target_quality else "Best"

            self.tree.insert(
                "",
                "end",
                values=(ps.song.title, ps.song.artist, action_str, src_name, q_str),
                tags=("download",),
            )

        for ps in plan.owned_songs:
            self.tree.insert(
                "",
                "end",
                values=(ps.song.title, ps.song.artist, "Skipped (Owned)", "-", f"{ps.song.quality_kbps or '?'} kbps"),
                tags=("owned",),
            )

        for s in plan.unresolvable:
            self.tree.insert(
                "",
                "end",
                values=(s.title, s.artist, "Unavailable", "-", "N/A"),
                tags=("unavail",),
            )

        self.tree.tag_configure("download", foreground="#81c784")
        self.tree.tag_configure("owned", foreground="#888888")
        self.tree.tag_configure("unavail", foreground="#e57373")

        # ── 3. Buttons Bar ─────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, height=50, corner_radius=0)
        btn_frame.grid(row=2, column=0, sticky="ew", padx=14, pady=10)
        btn_frame.grid_columnconfigure(1, weight=1)

        self.btn_confirm = ctk.CTkButton(
            btn_frame,
            text="🚀 Start Download",
            width=140,
            height=34,
            fg_color="#1a6b3c",
            hover_color="#236b4a",
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._confirm,
        )
        self.btn_confirm.pack(side="left", padx=6)

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=90,
            height=34,
            fg_color="#444444",
            hover_color="#555555",
            command=self.destroy,
        ).pack(side="right", padx=6)

    def _confirm(self) -> None:
        self.destroy()
        self.on_confirm()
