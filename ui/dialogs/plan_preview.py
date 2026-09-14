"""
Download Plan Preview dialog.

Presents explicit download breakdown before invoking the downloader.
Displays metrics, source selections, quality upgrades vs new downloads, and already downloaded items.
Buttons: [Start Download], [Cancel].
"""

from typing import Any, Callable, Optional
import tkinter as tk
from tkinter import ttk
import customtkinter as ctk

from library.planner import DownloadPlan
from ui import theme


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
        self.geometry("700x560")
        self.minsize(580, 460)
        self.grab_set()

        self.plan = plan
        self.on_confirm = on_confirm

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── 1. Summary Header Card ────────────────────────────────────
        header_frame = ctk.CTkFrame(
            self,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(14, 8))
        header_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header_frame,
            text="DOWNLOAD PLAN BREAKDOWN",
            font=theme.font_caption_bold(),
            text_color=theme.PRIMARY_LIGHT,
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(10, 6), sticky="w")

        selected_cnt = plan.unique_canonical or (len(plan.new_songs) + len(plan.owned) + len(plan.upgrades))
        owned_cnt = len(plan.owned)
        new_cnt = len(plan.new_songs)
        upgrades_cnt = len(plan.upgrades)
        actual_dl_cnt = plan.total_to_download if hasattr(plan, "total_to_download") else (new_cnt + upgrades_cnt)

        summary_text = (
            f"Selected Songs:      {selected_cnt:>5}\n"
            f"Already Downloaded:  {owned_cnt:>5}\n"
            f"New Downloads:       {new_cnt:>5}\n"
            f"Quality Upgrades:    {upgrades_cnt:>5}\n"
            f"-------------------------------\n"
            f"Actual Downloads:    {actual_dl_cnt:>5}"
        )

        ctk.CTkLabel(
            header_frame,
            text=summary_text,
            font=ctk.CTkFont(family="Consolas", size=11),
            justify="left",
            text_color=theme.TEXT_SECONDARY,
        ).grid(row=1, column=0, padx=16, pady=(0, 10), sticky="w")

        # ── 2. Detailed Table Preview ──────────────────────────────────
        table_frame = ctk.CTkFrame(
            self,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        table_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=6)
        table_frame.grid_rowconfigure(0, weight=1)
        table_frame.grid_columnconfigure(0, weight=1)

        style = ttk.Style()
        style.configure(
            "PlanTree.Treeview",
            background=theme.SURFACE,
            foreground=theme.TEXT_PRIMARY,
            fieldbackground=theme.SURFACE,
            rowheight=26,
            font=("Segoe UI", 9),
            borderwidth=0,
        )
        style.configure(
            "PlanTree.Treeview.Heading",
            background=theme.SURFACE_ELEVATED,
            foreground=theme.TEXT_SECONDARY,
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
        self.tree.column("type", width=130, anchor="center")
        self.tree.column("source", width=110, anchor="w")
        self.tree.column("quality", width=90, anchor="center")

        self.tree.grid(row=0, column=0, sticky="nsew", padx=2, pady=2)

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        vsb.grid(row=0, column=1, sticky="ns", padx=(0, 2), pady=2)
        self.tree.configure(yscrollcommand=vsb.set)

        # Populate rows: New Downloads
        for ps in plan.new_songs:
            title = ps.song.name if hasattr(ps.song, "name") else getattr(ps.song, "title", str(ps.song))
            artist = getattr(ps.song, "artist", None) or getattr(ps.song, "album_name", "-") or "-"
            src_name = ps.primary.source_name if ps.primary else (ps.source_name or "-")
            q_str = ps.primary.quality_str if ps.primary else "320 kbps"

            self.tree.insert(
                "",
                "end",
                values=(title, artist, "New Download", src_name, q_str),
                tags=("download",),
            )

        # Populate rows: Upgrades
        for up in plan.upgrades:
            title = up.song.name if hasattr(up.song, "name") else up.existing.title
            artist = getattr(up.song, "artist", None) or up.existing.artist or "-"
            src_name = up.source_name or (up.new_source.source_name if up.new_source else "-")
            q_str = up.new_source.quality_str if up.new_source else "320 kbps"

            self.tree.insert(
                "",
                "end",
                values=(title, artist, f"Upgrade (+{up.quality_gain}k)", src_name, q_str),
                tags=("upgrade",),
            )

        # Populate rows: Already Downloaded Songs
        for s in plan.owned:
            title = s.title if hasattr(s, "title") else (s.song.name if hasattr(s, "song") else str(s))
            artist = getattr(s, "artist", "-") or "-"
            q_val = getattr(s, "quality_kbps", "320")

            self.tree.insert(
                "",
                "end",
                values=(title, artist, "Already Downloaded", "-", f"{q_val} kbps"),
                tags=("owned",),
            )

        self.tree.tag_configure("download", foreground=theme.SUCCESS_LIGHT)
        self.tree.tag_configure("upgrade", foreground=theme.ACCENT_PURPLE)
        self.tree.tag_configure("owned", foreground=theme.TEXT_DIM)

        # ── 3. Buttons Bar ─────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(self, height=48, fg_color="transparent")
        btn_frame.grid(row=2, column=0, sticky="ew", padx=16, pady=10)

        self.btn_confirm = ctk.CTkButton(
            btn_frame,
            text="🚀 Start Download",
            width=140,
            height=32,
            fg_color=theme.SUCCESS,
            hover_color=theme.SUCCESS_BG,
            font=theme.font_caption_bold(),
            command=self._confirm,
        )
        self.btn_confirm.pack(side="left")

        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=80,
            height=32,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            font=theme.font_caption(),
            command=self.destroy,
        ).pack(side="right")

    def _confirm(self) -> None:
        self.destroy()
        self.on_confirm()
