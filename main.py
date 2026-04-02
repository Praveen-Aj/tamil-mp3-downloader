#!/usr/bin/env python3
"""
Tamil MP3 Downloader v3.0
Entry point with a clean, rich-powered CLI.
"""

import sys
from pathlib import Path
from typing import List, Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.spinner import Spinner
from rich.status import Status
from rich.table import Table
from rich.text import Text

from config.settings import settings
from downloaders.http_downloader import HTTPDownloader
from models.song import Album, Song
from scrapers.isaimini import IsaiminiScraper
from scrapers.masstamilan import MassTamilanScraper
from utils.logger import logger

console = Console()


# ─────────────────────────────────────────────────────────────────────────────
# UI helpers
# ─────────────────────────────────────────────────────────────────────────────

def _header():
    console.print(
        Panel(
            Text.assemble(
                ("🎵  Tamil MP3 Downloader   ", "bold yellow"),
                ("v3.0  ", "bold cyan"),
                ("• 2025 / 2026 Songs  •  320 kbps  •  Concurrent Downloads", "dim white"),
            ),
            expand=True,
            border_style="cyan",
            padding=(0, 2),
        )
    )


def _rule(title: str = ""):
    console.print(Rule(title, style="dim cyan"))


def _ask(prompt: str, choices: Optional[List[str]] = None, default: str = "") -> str:
    try:
        return Prompt.ask(f"[bold cyan]  › {prompt}[/]", choices=choices, default=default)
    except (EOFError, KeyboardInterrupt):
        console.print("\n[green]👋  Goodbye![/]")
        sys.exit(0)


def _yn(prompt: str) -> bool:
    answer = _ask(prompt + " [y/n]", choices=["y", "n", "Y", "N"], default="y")
    return answer.lower() == "y"


# ─────────────────────────────────────────────────────────────────────────────
# Album table
# ─────────────────────────────────────────────────────────────────────────────

def _show_album_table(albums: List[Album], page: int, page_size: int):
    start = (page - 1) * page_size
    end   = start + page_size
    page_albums = albums[start:end]
    total_pages = (len(albums) + page_size - 1) // page_size

    tbl = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="dim cyan",
        row_styles=["", "dim"],
        expand=False,
    )
    tbl.add_column("#",    style="cyan bold", width=4,  justify="right")
    tbl.add_column("Album Name",              width=40)
    tbl.add_column("Year",  style="yellow",  width=6,  justify="center")
    tbl.add_column("Songs", style="green",   width=7,  justify="center")

    for i, album in enumerate(page_albums, start + 1):
        sc = str(album.song_count) if album.song_count else "?"
        tbl.add_row(str(i), album.display_name, album.year_str, sc)

    console.print(tbl)
    console.print(
        f"  [dim]Page {page}/{total_pages}  "
        f"— Albums {start+1}–{min(end, len(albums))} of {len(albums)}[/]"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Song table
# ─────────────────────────────────────────────────────────────────────────────

def _show_song_table(songs: List[Song]):
    tbl = Table(
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
        expand=False,
    )
    tbl.add_column("#",       style="cyan bold",  width=4,  justify="right")
    tbl.add_column("Song",                         width=42)
    tbl.add_column("Quality", style="green",       width=9,  justify="center")
    tbl.add_column("Size",    style="yellow",      width=9,  justify="right")

    for i, s in enumerate(songs, 1):
        q_color = s.quality_color
        name_text = (
            Text("📦  " + s.display_name, style="bold yellow")
            if s.is_zip
            else Text("🎵  " + s.display_name)
        )
        tbl.add_row(
            str(i),
            name_text,
            Text(s.quality if s.quality != "unknown" else "?", style=f"bold {q_color}"),
            s.size_str,
        )

    console.print(tbl)


# ─────────────────────────────────────────────────────────────────────────────
# Selection parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_selection(raw: str, items: list) -> list:
    """
    Parse "1", "1,3,5", "2-4", "all" → list of selected items.
    Returns [] on "0" / "back".
    """
    raw = raw.strip().lower()
    if raw in ("0", "back", "b"):
        return []
    if raw in ("all", "a"):
        return list(items)

    selected = []
    for part in raw.split(","):
        part = part.strip()
        if "-" in part and not part.startswith("-"):
            try:
                lo, hi = part.split("-", 1)
                selected.extend(items[int(lo) - 1 : int(hi)])
            except (ValueError, IndexError):
                pass
        else:
            try:
                selected.append(items[int(part) - 1])
            except (ValueError, IndexError):
                pass

    return selected


# ─────────────────────────────────────────────────────────────────────────────
# Main app
# ─────────────────────────────────────────────────────────────────────────────

class TamilMP3Downloader:

    PAGE_SIZE = 10   # albums per page

    def __init__(self):
        self.isaimini_scraper = IsaiminiScraper(settings.isaimini_url)
        self.masstamilan_scraper = MassTamilanScraper(settings.get("sources.masstamilan.base_url"))
        self.downloader = HTTPDownloader(
            settings.output_dir,
            max_workers=settings.get("download.max_workers", 3),
        )

    # ── main loop ──────────────────────────────────────────────────────────

    def run(self):
        console.clear()
        _header()
        console.print()

        while True:
            _rule("  Main Menu  ")
            console.print(
                "  [cyan]1[/]  IsaiminiHQ  [dim]— Latest 2025 / 2026 songs[/]  [bold yellow]⭐ Recommended[/]\n"
                "  [cyan]2[/]  MassTamilan  [dim]— Latest releases 2025 / 2026[/]\n"
                "  [cyan]3[/]  FriendsTamilMP3  [dim]— Classic songs  (coming soon)[/]\n"
                "  [cyan]4[/]  Settings\n"
                "  [cyan]5[/]  Exit\n"
            )
            choice = _ask("Choose", choices=["1", "2", "3", "4", "5"])

            if choice == "1":
                console.clear()
                _header()
                self._source_flow("IsaiminiHQ", self.isaimini_scraper)
            elif choice == "2":
                console.clear()
                _header()
                self._source_flow("MassTamilan", self.masstamilan_scraper)
            elif choice == "3":
                console.clear()
                _header()
                console.print("[yellow]  FriendsTamilMP3 support coming soon![/]")
            elif choice == "4":
                self._settings_menu()
            elif choice == "5":
                console.print("\n[green]👋  Goodbye![/]\n")
                break

    # ── source selector ─────────────────────────────────────────────────

    def _source_flow(self, source_name: str, scraper):
        self.scraper = scraper
        _rule(f"  {source_name}  ")

        # Category selection
        console.print(
            "  [cyan]1[/]  Latest  (newest releases)  [bold yellow]⭐[/]\n"
            "  [cyan]2[/]  2026 songs\n"
            "  [cyan]3[/]  2025 songs\n"
            "  [cyan]0[/]  Back\n"
        )
        cat_choice = _ask("Category", choices=["0", "1", "2", "3"], default="1")
        if cat_choice == "0":
            return

        cat_map   = {"1": "latest", "2": "2026", "3": "2025"}
        category  = cat_map[cat_choice]

        # How many pages to scrape
        pages_str = _ask("Load how many pages of albums? [1–5]", default="2")
        try:
            max_pages = max(1, min(5, int(pages_str)))
        except ValueError:
            max_pages = 2

        # Fetch albums
        albums: List[Album] = []
        with Status(
            "[bold cyan]  Fetching albums…[/]",
            spinner="dots",
            console=console,
        ):
            try:
                self.scraper._init_browser()
                albums = self.scraper.get_albums(category, max_pages=max_pages)
            except Exception as e:
                logger.error(f"Album fetch error: {e}")

        if not albums:
            console.print(
                "[red]  ❌  No albums found. The site may be down or selectors have changed.[/]"
            )
            return

        # Album browsing loop
        page = 1
        while True:
            console.print()
            _rule(f"  Albums — {category.upper()}  ")
            _show_album_table(albums, page, self.PAGE_SIZE)

            total_pages = (len(albums) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
            nav_hint = ""
            if total_pages > 1:
                nav_hint = "  [dim]n=next page  p=prev[/]  "

            raw = _ask(
                f"Select album(s){nav_hint}  [dim]1…{len(albums)}  1,3  2-5  all  0=back[/]",
                default="0",
            )
            if raw.strip().lower() in ("0", "back", "b"):
                return
            if raw.strip().lower() in ("n", "next") and page < total_pages:
                page += 1;  continue
            if raw.strip().lower() in ("p", "prev") and page > 1:
                page -= 1;  continue

            selected = _parse_selection(raw, albums)
            if not selected:
                console.print("[yellow]  No valid selection.[/]")
                continue

            for album in selected:
                self._download_album_flow(album)

            if not _yn("\n  Download another album?"):
                return

    # ── album download flow ────────────────────────────────────────────────

    def _download_album_flow(self, album: Album):
        console.print()
        console.print(
            Panel(
                Text.assemble(
                    ("📀  ", "yellow"),
                    (album.display_name, "bold white"),
                    (f"   {album.year_str}", "dim"),
                ),
                border_style="blue",
                expand=False,
            )
        )

        # Fetch songs
        songs: List[Song] = []
        with Status(
            "[bold cyan]  Fetching track list…[/]",
            spinner="dots",
            console=console,
        ):
            try:
                songs = self.scraper.get_songs(album)
            except Exception as e:
                logger.error(f"Song fetch error for {album.display_name}: {e}")

        if not songs:
            console.print("[red]  ❌  No songs found for this album.[/]")
            return

        # Update song_count on album
        album.song_count = len(songs)

        console.print()
        _show_song_table(songs)
        console.print()

        # How to download
        zips = [s for s in songs if s.is_zip]
        mp3s = [s for s in songs if not s.is_zip]

        if zips and mp3s:
            console.print(
                "  [cyan]1[/]  Download ZIP only  [dim](all songs in one file, fastest)[/]\n"
                "  [cyan]2[/]  Download individual MP3s  [dim](320 kbps priority)[/]\n"
                "  [cyan]3[/]  Download both\n"
                "  [cyan]0[/]  Skip this album\n"
            )
            choice = _ask("Download mode", choices=["0", "1", "2", "3"], default="1")
            if choice == "0":
                return
            elif choice == "1":
                to_download = zips
            elif choice == "2":
                to_download = mp3s
            else:
                to_download = songs
        elif zips:
            if not _yn("  Download ZIP archive?"):
                return
            to_download = zips
        else:
            if not _yn(f"  Download all {len(mp3s)} MP3s?"):
                return
            to_download = mp3s

        # Set album_name on all selected songs
        for s in to_download:
            s.album_name = album.safe_dirname

        console.print()
        _rule(f"  Downloading: {album.display_name}  ")

        results = self.downloader.download_concurrent(
            to_download,
            album_name=album.safe_dirname,
            max_workers=settings.get("download.max_workers", 3),
        )

        ok  = sum(1 for r in results if r.success)
        err = len(results) - ok
        size_total = sum(r.size_downloaded for r in results if r.size_downloaded)
        size_mb = size_total / (1024 * 1024)

        console.print()
        _rule()
        console.print(
            f"  [bold]Done![/]  "
            f"[green]✓ {ok} downloaded[/]"
            + (f"   [red]✗ {err} failed[/]" if err else "")
            + f"   [yellow]{size_mb:.1f} MB[/]"
        )
        console.print(f"  [dim]Saved to:  {settings.output_dir / 'IsaiminiHQ' / album.safe_dirname}[/]")

        # Show failures if any
        if err:
            for r in results:
                if not r.success:
                    console.print(f"    [red]✗[/] {r.song_name}  [dim]{r.error_message}[/]")

    # ── settings menu ─────────────────────────────────────────────────────

    def _settings_menu(self):
        _rule("  Settings  ")
        console.print(
            f"  [dim]Output directory  :[/]  {settings.output_dir}\n"
            f"  [dim]Max workers        :[/]  {settings.get('download.max_workers', 3)}\n"
            f"  [dim]Per-file retries   :[/]  {settings.get('download.retries', 3)}\n"
        )
        if _yn("  Change max concurrent downloads?"):
            w = _ask("  Workers (1–8)", default="3")
            try:
                settings.set("download.max_workers", max(1, min(8, int(w))))
                console.print(f"  [green]✓  Workers set to {settings.get('download.max_workers')}[/]")
            except ValueError:
                pass


# ─────────────────────────────────────────────────────────────────────────────

def main():
    try:
        app = TamilMP3Downloader()
        app.run()
    except KeyboardInterrupt:
        console.print("\n[green]👋  Goodbye![/]\n")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal: {e}", exc_info=True)
        console.print_exception()
        sys.exit(1)
    finally:
        # Always close playwright browser
        try:
            app.scraper._close_browser()
        except Exception:
            pass


if __name__ == "__main__":
    main()
