"""
Song Details / Duplicate Inspector dialog.

Provides explainable identity details for songs:
- Metadata & Music Library State (DOWNLOADED / NOT DOWNLOADED)
- Discovery Contexts (where/which categories this song was discovered)
- Available Source Variants & Quality
- Download Planner Decision & Reasoning
- Direct Actions: [Open Folder], [Delete File], [Download Song]
"""

from typing import Dict, List, Any, Optional
import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

from library.models import LibrarySong, SongSource, DiscoveryContext, SongState
from library.planner import DownloadPlan, SourceSelection
from ui import theme


class SongDetailsDialog(ctk.CTkToplevel):
    """
    Explainable duplicate inspector and song identity dialog.
    """

    def __init__(
        self,
        master: Any,
        song: LibrarySong,
        sources: List[SongSource],
        contexts: List[DiscoveryContext],
        planner_decision: Optional[DownloadPlan] = None,
        service: Optional[Any] = None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.title(f"🎵 Song Details — {song.title}")
        self.geometry("720x620")
        self.minsize(580, 480)
        self.grab_set()

        self.song = song
        self.sources = sources
        self.contexts = contexts
        self.planner_decision = planner_decision
        self.service = service

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent", corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew", padx=16, pady=14)
        scroll.grid_columnconfigure(0, weight=1)

        # ── 1. Song Identity Header ──────────────────────────────────
        header_frame = ctk.CTkFrame(
            scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        header_frame.pack(fill="x", pady=(0, 10))
        header_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header_frame,
            text=song.title,
            font=theme.font_hero(),
            text_color=theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, columnspan=2, padx=16, pady=(12, 2), sticky="w")

        artist_album = f"Artist: {song.artist or 'Unknown'}  •  Album: {song.album or 'Tamil Music'}  •  Year: {song.year or 'N/A'}"
        ctk.CTkLabel(
            header_frame,
            text=artist_album,
            font=theme.font_body(),
            text_color=theme.TEXT_MUTED,
        ).grid(row=1, column=0, columnspan=2, padx=16, pady=(0, 12), sticky="w")

        # ── 2. Library State ──────────────────────────────────────────
        state_frame = ctk.CTkFrame(
            scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        state_frame.pack(fill="x", pady=5)

        is_downloaded = (song.state == SongState.OWNED)
        state_color = theme.SUCCESS_LIGHT if is_downloaded else theme.WARNING_LIGHT

        ctk.CTkLabel(
            state_frame,
            text="MUSIC LIBRARY STATUS",
            font=theme.font_caption_bold(),
            text_color=state_color,
        ).pack(anchor="w", padx=16, pady=(10, 4))

        state_str = "DOWNLOADED (Saved in local music library)" if is_downloaded else "NOT DOWNLOADED (Ready to download)"
        file_info = f"File: {song.file_path}" if song.file_path else "Local File: Not downloaded yet"
        quality_info = f"Quality: {song.quality_kbps} kbps" if song.quality_kbps else "Quality: 320 kbps (Standard)"

        ctk.CTkLabel(
            state_frame,
            text=f"Status: {state_str}\n{quality_info}\n{file_info}",
            font=theme.font_caption(),
            text_color=theme.TEXT_SECONDARY,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(0, 8))

        # Action buttons for this song
        act_row = ctk.CTkFrame(state_frame, fg_color="transparent")
        act_row.pack(anchor="w", padx=16, pady=(0, 10))

        if is_downloaded:
            ctk.CTkButton(
                act_row,
                text="📁 Open Folder",
                font=theme.font_caption_bold(),
                height=26,
                width=95,
                fg_color=theme.SURFACE_ELEVATED,
                hover_color=theme.SURFACE_HOVER,
                text_color=theme.TEXT_SECONDARY,
                command=self._open_folder,
            ).pack(side="left", padx=(0, 6))

            ctk.CTkButton(
                act_row,
                text="🗑️ Delete File",
                font=theme.font_caption_bold(),
                height=26,
                width=85,
                fg_color=theme.SURFACE_ELEVATED,
                hover_color=theme.ERROR,
                text_color=theme.TEXT_SECONDARY,
                command=self._delete_file,
            ).pack(side="left")
        else:
            ctk.CTkButton(
                act_row,
                text="⬇ Download Song",
                font=theme.font_caption_bold(),
                height=26,
                width=120,
                fg_color=theme.PRIMARY,
                hover_color=theme.PRIMARY_HOVER,
                text_color=theme.TEXT_PRIMARY,
                command=self._download_song,
            ).pack(side="left")

        # ── 3. Discovery Contexts (Found In) ──────────────────────────
        ctx_frame = ctk.CTkFrame(
            scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        ctx_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(
            ctx_frame,
            text="DISCOVERY CONTEXTS (Found In)",
            font=theme.font_caption_bold(),
            text_color=theme.PRIMARY_LIGHT,
        ).pack(anchor="w", padx=16, pady=(10, 4))

        if contexts:
            for ctx in contexts:
                ctx_detail = f"Album: '{ctx.album_name}'" if ctx.album_name else f"Category: '{ctx.category or 'General'}'"
                ctx_text = f"• Source: {ctx.source_name} | {ctx_detail}"
                ctk.CTkLabel(
                    ctx_frame, text=ctx_text, font=theme.font_caption(), text_color=theme.TEXT_SECONDARY
                ).pack(anchor="w", padx=20, pady=2)
        else:
            ctk.CTkLabel(
                ctx_frame, text="Discovered via URL import or search.", font=theme.font_caption(), text_color=theme.TEXT_DIM
            ).pack(anchor="w", padx=20, pady=2)

        ctk.CTkLabel(ctx_frame, text="", height=4).pack()

        # ── 4. Available Source Variants ──────────────────────────────
        sources_frame = ctk.CTkFrame(
            scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE,
            border_width=1,
            border_color=theme.BORDER,
        )
        sources_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(
            sources_frame,
            text="AVAILABLE AUDIO SOURCES",
            font=theme.font_caption_bold(),
            text_color=theme.ACCENT_PURPLE,
        ).pack(anchor="w", padx=16, pady=(10, 4))

        if sources:
            for src in sources:
                q_text = f"{src.quality_kbps} kbps" if src.quality_kbps else "320 kbps"
                src_line = (
                    f"• {src.source_name} — {q_text}\n"
                    f"  Format: {src.file_type or 'mp3'} | Status: {'Available' if src.is_available else 'Unavailable'}"
                )
                ctk.CTkLabel(
                    sources_frame,
                    text=src_line,
                    font=theme.font_caption(),
                    justify="left",
                    text_color=theme.TEXT_SECONDARY,
                ).pack(anchor="w", padx=20, pady=3)
        else:
            ctk.CTkLabel(
                sources_frame, text="No extra source variants registered.", font=theme.font_caption(), text_color=theme.TEXT_DIM
            ).pack(anchor="w", padx=20, pady=2)

        ctk.CTkLabel(sources_frame, text="", height=4).pack()

        # ── 5. Planner Decision & Reason ──────────────────────────────
        planner_frame = ctk.CTkFrame(
            scroll,
            corner_radius=theme.RADIUS_MD,
            fg_color=theme.SURFACE_ELEVATED,
            border_width=1,
            border_color=theme.BORDER,
        )
        planner_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(
            planner_frame,
            text="DOWNLOAD STATUS & RECOMMENDATION",
            font=theme.font_caption_bold(),
            text_color=theme.WARNING_LIGHT,
        ).pack(anchor="w", padx=16, pady=(10, 4))

        reason_text = "Match verified and ready for download."
        if planner_decision:
            if hasattr(planner_decision, "owned") and any(s.id == song.id for s in planner_decision.owned):
                reason_text = "Status: Already Downloaded in music library."
            elif hasattr(planner_decision, "new_songs") and planner_decision.new_songs:
                reason_text = "Status: Ready to download from preferred audio provider."
            elif getattr(planner_decision, "upgrades", None) and any(u.existing.id == song.id for u in planner_decision.upgrades):
                reason_text = "Status: Quality upgrade available (320 kbps master found)."

        ctk.CTkLabel(
            planner_frame,
            text=reason_text,
            font=theme.font_caption(),
            justify="left",
            text_color=theme.TEXT_SECONDARY,
        ).pack(anchor="w", padx=20, pady=(0, 10))

        # Bottom Close button
        ctk.CTkButton(
            self,
            text="Close",
            font=theme.font_body_bold(),
            width=100,
            height=30,
            fg_color=theme.SURFACE_ELEVATED,
            hover_color=theme.SURFACE_HOVER,
            text_color=theme.TEXT_SECONDARY,
            command=self.destroy,
        ).grid(row=1, column=0, pady=10)

    def _open_folder(self) -> None:
        if self.service:
            self.service.open_path_in_explorer(self.song.file_path)

    def _delete_file(self) -> None:
        if messagebox.askyesno("Delete Song", f"Delete \"{self.song.title}\"?\n\nThis will remove the downloaded file from your computer."):
            if self.service:
                self.service.delete_downloaded_song(self.song.id, delete_physical_file=True)
            self.destroy()

    def _download_song(self) -> None:
        if self.service:
            plan = self.service.preview_download_plan([self.song.id])
            self.service.execute_download_plan(plan, run_async=True)
        self.destroy()
