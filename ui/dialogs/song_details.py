"""
Song Details / Duplicate Inspector dialog.

Provides explainable identity details for canonical songs:
- Metadata & Library State
- Discovery Contexts (where/which categories this song was discovered)
- Available Source Variants & Quality
- Download Planner Decision & Reasoning
"""

from typing import Dict, List, Any, Optional
import tkinter as tk
import customtkinter as ctk

from library.models import LibrarySong, SongSource, DiscoveryContext, SongState
from library.planner import DownloadPlan, SourceSelection


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
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self.title(f"🎵 Song Details — {song.title}")
        self.geometry("750x650")
        self.minsize(600, 500)
        self.grab_set()

        self.song = song
        self.sources = sources
        self.contexts = contexts
        self.planner_decision = planner_decision

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(self, corner_radius=0)
        scroll.grid(row=0, column=0, sticky="nsew", padx=12, pady=12)
        scroll.grid_columnconfigure(0, weight=1)

        # ── 1. Canonical Identity Section ────────────────────────────
        header_frame = ctk.CTkFrame(scroll, corner_radius=6, fg_color="#252538")
        header_frame.pack(fill="x", pady=(0, 10))
        header_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            header_frame,
            text=song.title,
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color="#ffffff",
        ).grid(row=0, column=0, columnspan=2, padx=14, pady=(12, 4), sticky="w")

        artist_album = f"Artist: {song.artist}  •  Album: {song.album or 'Unknown'}  •  Year: {song.year or 'N/A'}"
        ctk.CTkLabel(
            header_frame,
            text=artist_album,
            font=ctk.CTkFont(size=12),
            text_color="#bbbbdd",
        ).grid(row=1, column=0, columnspan=2, padx=14, pady=(0, 12), sticky="w")

        # ── 2. Library State ──────────────────────────────────────────
        state_frame = ctk.CTkFrame(scroll, corner_radius=6)
        state_frame.pack(fill="x", pady=6)

        ctk.CTkLabel(
            state_frame,
            text="LIBRARY STATE",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#81c784" if song.state == SongState.OWNED else "#ffa726",
        ).pack(anchor="w", padx=12, pady=(10, 4))

        state_str = "OWNED (In local library)" if song.state == SongState.OWNED else "UNOWNED (Available for download)"
        file_info = f"File: {song.file_path}" if song.file_path else "Local File: None"
        quality_info = f"Quality: {song.quality_kbps} kbps" if song.quality_kbps else "Quality: Unknown"

        ctk.CTkLabel(
            state_frame,
            text=f"Status: {state_str}\n{quality_info}\n{file_info}",
            font=ctk.CTkFont(size=11),
            justify="left",
        ).pack(anchor="w", padx=12, pady=(0, 10))

        # ── 3. Discovery Contexts (Found In) ──────────────────────────
        ctx_frame = ctk.CTkFrame(scroll, corner_radius=6)
        ctx_frame.pack(fill="x", pady=6)

        ctk.CTkLabel(
            ctx_frame,
            text="DISCOVERY CONTEXTS (Found In)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#90caf9",
        ).pack(anchor="w", padx=12, pady=(10, 4))

        if contexts:
            for ctx in contexts:
                ctx_text = f"• Source: {ctx.source_name} | Category: {ctx.category} | Context: {ctx.context_type}"
                ctk.CTkLabel(
                    ctx_frame, text=ctx_text, font=ctk.CTkFont(size=11), text_color="#d0d0d0"
                ).pack(anchor="w", padx=16, pady=2)
        else:
            ctk.CTkLabel(
                ctx_frame, text="No discovery context recorded.", font=ctk.CTkFont(size=11), text_color="#888888"
            ).pack(anchor="w", padx=16, pady=2)

        ctk.CTkLabel(ctx_frame, text="", height=4).pack()

        # ── 4. Available Source Variants ──────────────────────────────
        sources_frame = ctk.CTkFrame(scroll, corner_radius=6)
        sources_frame.pack(fill="x", pady=6)

        ctk.CTkLabel(
            sources_frame,
            text="AVAILABLE SOURCE VARIANTS (Duplicates Collapsed)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ce93d8",
        ).pack(anchor="w", padx=12, pady=(10, 4))

        if sources:
            for src in sources:
                q_text = f"{src.quality_kbps} kbps" if src.quality_kbps else "Unknown quality"
                src_line = (
                    f"• {src.source_name} — {q_text}\n"
                    f"  URL: {src.source_url or 'N/A'}\n"
                    f"  Format: {src.audio_format or 'mp3'} | Download Ref: {src.download_reference or 'N/A'}"
                )
                ctk.CTkLabel(
                    sources_frame,
                    text=src_line,
                    font=ctk.CTkFont(size=11),
                    justify="left",
                    text_color="#e0e0e0",
                ).pack(anchor="w", padx=16, pady=4)
        else:
            ctk.CTkLabel(
                sources_frame, text="No source variants registered.", font=ctk.CTkFont(size=11), text_color="#888888"
            ).pack(anchor="w", padx=16, pady=2)

        ctk.CTkLabel(sources_frame, text="", height=4).pack()

        # ── 5. Planner Decision & Reason ──────────────────────────────
        planner_frame = ctk.CTkFrame(scroll, corner_radius=6, fg_color="#1e2c38")
        planner_frame.pack(fill="x", pady=6)

        ctk.CTkLabel(
            planner_frame,
            text="DOWNLOAD PLANNER DECISION",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#ffb74d",
        ).pack(anchor="w", padx=12, pady=(10, 4))

        reason_text = "No plan evaluated yet."
        if planner_decision:
            if planner_decision.owned_songs and any(s.song.id == song.id for s in planner_decision.owned_songs):
                reason_text = "Decision: Excluded from download.\nReason: Song is already OWNED in library."
            elif planner_decision.new_songs:
                matching = [s for s in planner_decision.new_songs if s.song.id == song.id]
                if matching:
                    ps = matching[0]
                    target_q = ps.target_quality or "Best available"
                    src_name = ps.primary.source_name if ps.primary else "None"
                    reason_text = (
                        f"Decision: Selected for download.\n"
                        f"Selected Source: {src_name} ({target_q} kbps)\n"
                        f"Reason: Preferred source and quality matching user criteria."
                    )
            elif planner_decision.unresolvable:
                reason_text = "Decision: Cannot download.\nReason: No usable sources or audio URLs available."

        ctk.CTkLabel(
            planner_frame,
            text=reason_text,
            font=ctk.CTkFont(size=11),
            justify="left",
            text_color="#fff3e0",
        ).pack(anchor="w", padx=16, pady=(0, 10))

        # Close button
        ctk.CTkButton(
            self, text="Close Inspector", width=120, height=32, command=self.destroy
        ).grid(row=1, column=0, pady=10)
