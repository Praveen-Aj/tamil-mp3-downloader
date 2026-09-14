"""
Import View (Phase 9).

Local MP3 file scanner and canonical library importer.
Extracts ID3 tags, computes canonical identity, updates SQLite, and sets state to OWNED.
Deduplicates future discovery queries automatically.
"""

from pathlib import Path
import threading
from typing import Dict, Any, Callable, Optional
import tkinter as tk
from tkinter import filedialog
import customtkinter as ctk

from ui.services.library_service import LibraryService


class ImportView(ctk.CTkFrame):
    """
    Import local audio files view.
    """

    def __init__(
        self,
        master: Any,
        service: LibraryService,
        **kwargs,
    ):
        super().__init__(master, corner_radius=0, **kwargs)
        self.service = service

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # ── Header ────────────────────────────────────────────────────
        header = ctk.CTkFrame(self, height=50, corner_radius=0, fg_color="#181824")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_propagate(False)

        ctk.CTkLabel(
            header,
            text="📂  Import Existing Local MP3s",
            font=ctk.CTkFont(size=16, weight="bold"),
        ).pack(side="left", padx=16, pady=10)

        # ── Controls & Results Card ────────────────────────────────────
        scroll = ctk.CTkScrollableFrame(self, corner_radius=0)
        scroll.grid(row=1, column=0, sticky="nsew", padx=16, pady=16)
        scroll.grid_columnconfigure(0, weight=1)

        ctrl_card = ctk.CTkFrame(scroll, corner_radius=6, fg_color="#1c1c2e")
        ctrl_card.pack(fill="x", pady=(0, 12))

        ctk.CTkLabel(
            ctrl_card,
            text="SELECT LOCAL MUSIC DIRECTORY",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#90caf9",
        ).pack(anchor="w", padx=16, pady=(12, 6))

        dir_frame = ctk.CTkFrame(ctrl_card, fg_color="transparent")
        dir_frame.pack(fill="x", padx=16, pady=(0, 12))
        dir_frame.grid_columnconfigure(0, weight=1)

        self.dir_var = tk.StringVar(value=str(Path.home() / "Music"))
        self.entry_dir = ctk.CTkEntry(dir_frame, textvariable=self.dir_var, height=32)
        self.entry_dir.grid(row=0, column=0, sticky="ew", padx=(0, 8))

        ctk.CTkButton(
            dir_frame, text="Browse…", width=90, height=32, command=self._browse_directory
        ).grid(row=0, column=1)

        self.btn_scan = ctk.CTkButton(
            scroll,
            text="🔍 Scan Directory & Import to Library",
            font=ctk.CTkFont(size=13, weight="bold"),
            height=40,
            fg_color="#1f538d",
            hover_color="#2a6abf",
            command=self._start_import_thread,
        )
        self.btn_scan.pack(fill="x", pady=6)

        self.progress = ctk.CTkProgressBar(scroll, height=10)
        self.progress.set(0)
        self.progress.pack(fill="x", pady=4)
        self.progress.pack_forget()

        # Results Summary Box
        results_card = ctk.CTkFrame(scroll, corner_radius=6, fg_color="#1c1c2e")
        results_card.pack(fill="x", pady=12)

        ctk.CTkLabel(
            results_card,
            text="IMPORT SUMMARY & METRICS",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#81c784",
        ).pack(anchor="w", padx=16, pady=(12, 6))

        self.res_var = tk.StringVar(value="No import scan performed yet.")
        ctk.CTkLabel(
            results_card,
            textvariable=self.res_var,
            font=ctk.CTkFont(size=11),
            justify="left",
            text_color="#e0e0e0",
        ).pack(anchor="w", padx=16, pady=(0, 12))

    def _browse_directory(self) -> None:
        chosen = filedialog.askdirectory()
        if chosen:
            self.dir_var.set(chosen)

    def _start_import_thread(self) -> None:
        target_dir = Path(self.dir_var.get().strip())
        if not target_dir.exists():
            self.res_var.set("❌ Selected directory does not exist.")
            return

        self.btn_scan.configure(state="disabled")
        self.progress.pack(fill="x", pady=4)
        self.progress.configure(mode="indeterminate")
        self.progress.start()
        self.res_var.set("⏳ Extracting ID3 metadata and matching against SQLite canonical library...")

        def _worker():
            try:
                res = self.service.importer.import_directory(target_dir)
                self.after(0, lambda: self._on_success(res))
            except Exception as e:
                self.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _on_success(self, res: Dict[str, Any]) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self.btn_scan.configure(state="normal")

        msg = (
            f"✅ Import Scan Complete!\n"
            f"Files Scanned:  {res.get('scanned', 0):,}\n"
            f"Matched & Updated: {res.get('matched', 0):,}\n"
            f"New Canonical Songs: {res.get('imported', 0):,}\n"
            f"Unmatched Files: {res.get('unmatched', 0):,}"
        )
        self.res_var.set(msg)

    def _on_error(self, err: str) -> None:
        self.progress.stop()
        self.progress.pack_forget()
        self.btn_scan.configure(state="normal")
        self.res_var.set(f"❌ Import error: {err}")
