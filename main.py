#!/usr/bin/env python3
"""
Tamil MP3 Downloader v3.0
Entry point with a clean, rich-powered CLI.
"""

import sys
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, TypeVar

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.status import Status
from rich.table import Table
from rich.text import Text

from config.settings import settings
from downloaders.http_downloader import HTTPDownloader
from models.song import Album, Song
from scrapers.base import BaseScraper
from scrapers.friendstamilmp3 import FriendsTamilMP3Scraper
from scrapers.isaimini import IsaiminiScraper
from scrapers.masstamilan import MassTamilanScraper
from utils.logger import logger

console = Console()
T = TypeVar("T")


@dataclass
class SearchHit:
    """Single fuzzy-matched album result with source context."""

    album: Album
    scraper: BaseScraper
    source_name: str
    score: float


def _fuzzy_score(keyword: str, candidate: str) -> float:
    """
    Compute a fuzzy relevance score in [0, 1] for keyword vs album name.

    Prioritizes direct substring matches, then falls back to token and full
    sequence similarity.
    """
    kw = keyword.strip().lower()
    text = candidate.strip().lower()
    if not kw or not text:
        return 0.0

    if len(kw) <= 2:
        return 1.0 if kw in text else 0.0

    contains_bonus = 0.0
    if kw in text:
        contains_bonus = 0.25

    full_ratio = SequenceMatcher(None, kw, text).ratio()
    token_ratio = max((SequenceMatcher(None, kw, token).ratio() for token in text.split()), default=0.0)
    return min(1.0, max(full_ratio, token_ratio) + contains_bonus)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# UI helpers
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _header() -> None:
    console.print(
        Panel(
            Text.assemble(
                ("ðŸŽµ  Tamil MP3 Downloader   ", "bold yellow"),
                ("v3.0  ", "bold cyan"),
                ("â€¢ 2025 / 2026 Songs  â€¢  320 kbps  â€¢  Concurrent Downloads", "dim white"),
            ),
            expand=True,
            border_style="cyan",
            padding=(0, 2),
        )
    )


def _rule(title: str = "") -> None:
    console.print(Rule(title, style="dim cyan"))


def _ask(prompt: str, choices: Optional[List[str]] = None, default: str = "") -> str:
    try:
        return Prompt.ask(f"[bold cyan]  â€º {prompt}[/]", choices=choices, default=default)
    except (EOFError, KeyboardInterrupt):
        console.print("\n[green]ðŸ‘‹  Goodbye![/]")
        sys.exit(0)


def _yn(prompt: str) -> bool:
    answer = _ask(prompt + " [y/n]", choices=["y", "n", "Y", "N"], default="y")
    return answer.lower() == "y"


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Album table
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _show_album_table(albums: List[Album], page: int, page_size: int) -> None:
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
        f"â€” Albums {start+1}â€“{min(end, len(albums))} of {len(albums)}[/]"
    )


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Song table
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _show_search_table(results: List[SearchHit]) -> None:
    """Render fuzzy search results across all sources as a numbered table."""
    tbl = Table(
        box=box.ROUNDED,
        show_header=True,
        header_style="bold magenta",
        border_style="dim cyan",
        row_styles=["", "dim"],
        expand=False,
    )
    tbl.add_column("#", style="cyan bold", width=4, justify="right")
    tbl.add_column("Album Name", width=40)
    tbl.add_column("Year", style="yellow", width=6, justify="center")
    tbl.add_column("Source", style="bold cyan", width=12)
    tbl.add_column("Match", style="green", width=7, justify="right")

    for idx, hit in enumerate(results, 1):
        tbl.add_row(
            str(idx),
            hit.album.display_name,
            hit.album.year_str,
            hit.source_name,
            f"{int(hit.score * 100)}%",
        )
    console.print(tbl)


def _show_song_table(songs: List[Song]) -> None:
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
            Text("ðŸ“¦  " + s.display_name, style="bold yellow")
            if s.is_zip
            else Text("ðŸŽµ  " + s.display_name)
        )
        tbl.add_row(
            str(i),
            name_text,
            Text(s.quality if s.quality != "unknown" else "?", style=f"bold {q_color}"),
            s.size_str,
        )

    console.print(tbl)


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Selection parser
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _parse_selection(raw: str, items: Sequence[T]) -> List[T]:
    """
    Parse "1", "1,3,5", "2-4", "all" â†’ list of selected items.
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


def _is_back_choice(raw: str) -> bool:
    """Return True when user input means navigate back."""
    return raw.strip().lower() in ("0", "back", "b")


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Main app
# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class TamilMP3Downloader:

    PAGE_SIZE: int = 10   # albums per page

    def __init__(self) -> None:
        self.isaimini_scraper: IsaiminiScraper = IsaiminiScraper(settings.isaimini_url)
        self.masstamilan_scraper: MassTamilanScraper = MassTamilanScraper(
            settings.get("sources.masstamilan.base_url")
        )
        self.friendstamilmp3_scraper: FriendsTamilMP3Scraper = FriendsTamilMP3Scraper(
            settings.get("sources.friendstamilmp3.base_url")
        )
        self.scraper: BaseScraper = self.isaimini_scraper
        self.downloader: HTTPDownloader = HTTPDownloader(
            settings.output_dir,
            max_workers=settings.get("download.max_workers", 3),
            show_progress=settings.show_progress,
        )
        self._refresh_downloader_from_settings()

    def _refresh_downloader_from_settings(self) -> None:
        """Apply persisted runtime settings to downloader instance."""
        self.downloader.output_dir = settings.output_dir
        self.downloader.output_dir.mkdir(parents=True, exist_ok=True)
        self.downloader.max_workers = max(1, int(settings.get("download.max_workers", 3)))
        self.downloader.show_progress = settings.show_progress

    # â”€â”€ main loop â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def run(self) -> None:
        console.clear()
        _header()
        console.print()

        while True:
            _rule("  Main Menu  ")
            console.print(
                "  [cyan]1[/]  IsaiminiHQ  [dim]- Latest 2025 / 2026 songs[/]  [bold yellow]⭐ Recommended[/]\n"
                "  [cyan]2[/]  MassTamilan  [dim]- Latest releases 2025 / 2026[/]\n"
                "  [cyan]3[/]  FriendsTamilMP3  [dim]- Classic and curated hits[/]\n"
                "  [cyan]4[/]  Search  [dim]- Find albums across all sources[/]\n"
                "  [cyan]5[/]  Settings\n"
                "  [cyan]6[/]  Exit\n"
            )
            choice = _ask("Choose", choices=["1", "2", "3", "4", "5", "6"])

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
                self._source_flow("FriendsTamilMP3", self.friendstamilmp3_scraper)
            elif choice == "4":
                console.clear()
                _header()
                self._search_flow()
            elif choice == "5":
                self._settings_menu()
            elif choice == "6":
                console.print("\n[green]👋  Goodbye![/]\n")
                break
    # â”€â”€ source selector â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _source_flow(self, source_name: str, scraper: BaseScraper) -> None:
        self.scraper = scraper
        _rule(f"  {source_name}  ")

        # Category selection
        console.print(
            "  [cyan]1[/]  Latest  (newest releases)  [bold yellow]â­[/]\n"
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
        pages_str = _ask("Load how many pages of albums? [1â€“5]", default="2")
        try:
            max_pages = max(1, min(5, int(pages_str)))
        except ValueError:
            max_pages = 2

        # Fetch albums
        albums: List[Album] = []
        with Status(
            "[bold cyan]  Fetching albumsâ€¦[/]",
            spinner="dots",
            console=console,
        ):
            try:
                self.scraper._init_browser()
                albums = self.scraper.get_albums(category, max_pages=max_pages)
            except Exception:
                logger.exception("Album fetch failed for source=%s category=%s", source_name, category)

        if not albums:
            if source_name.lower().startswith("masstamilan"):
                console.print(
                    "[yellow]  âš ï¸  MassTamilan gave no results; fallback to IsaiminiHQ...[/]"
                )
                self.scraper = self.isaimini_scraper
                with Status(
                    "[bold cyan]  Fetching albums from IsaiminiHQâ€¦[/]",
                    spinner="dots",
                    console=console,
                ):
                    try:
                        albums = self.scraper.get_albums(category, max_pages=max_pages)
                    except Exception:
                        logger.exception("Fallback album fetch failed for category=%s", category)

            if not albums:
                console.print(
                    "[red]  âŒ  No albums found. The site may be down or selectors have changed.[/]"
                )
                return

        # Album browsing loop
        page = 1
        while True:
            console.print()
            _rule(f"  Albums â€” {category.upper()}  ")
            _show_album_table(albums, page, self.PAGE_SIZE)

            total_pages = (len(albums) + self.PAGE_SIZE - 1) // self.PAGE_SIZE
            nav_hint = ""
            if total_pages > 1:
                nav_hint = "  [dim]n=next page  p=prev[/]  "

            raw = _ask(
                f"Select album(s){nav_hint}  [dim]1â€¦{len(albums)}  1,3  2-5  all  0=back[/]",
                default="0",
            )
            if _is_back_choice(raw):
                return
            if raw.strip().lower() in ("n", "next") and page < total_pages:
                page += 1
                continue
            if raw.strip().lower() in ("p", "prev") and page > 1:
                page -= 1
                continue

            selected = _parse_selection(raw, albums)
            if not selected:
                console.print("[yellow]  No valid selection.[/]")
                continue

            for album in selected:
                self._download_album_flow(album)

            if not _yn("\n  Download another album?"):
                return

    def _collect_search_hits(self, keyword: str, max_pages: int) -> List[SearchHit]:
        """Fetch albums from all configured sources and return fuzzy matches."""
        sources = [
            (
                "IsaiminiHQ",
                self.isaimini_scraper,
                settings.get("sources.isaimini.categories", ["latest"]),
            ),
            (
                "MassTamilan",
                self.masstamilan_scraper,
                settings.get("sources.masstamilan.categories", ["latest"]),
            ),
            (
                "FriendsTamilMP3",
                self.friendstamilmp3_scraper,
                settings.get("sources.friendstamilmp3.categories", ["latest"]),
            ),
        ]

        matches: List[SearchHit] = []
        seen_urls: set[tuple[str, str]] = set()

        for source_name, scraper, raw_categories in sources:
            categories: List[str] = []
            if isinstance(raw_categories, list):
                categories = [str(c).strip() for c in raw_categories if str(c).strip()]
            if not categories:
                categories = ["latest"]
            if source_name == "MassTamilan":
                # This scraper currently uses /tamil-songs paging irrespective of category.
                categories = ["latest"]

            for category in categories:
                try:
                    albums = scraper.get_albums(category, max_pages=max_pages)
                except Exception:
                    logger.exception("Search fetch error source=%s category=%s", source_name, category)
                    continue

                for album in albums:
                    key = (source_name, album.url)
                    if key in seen_urls:
                        continue
                    seen_urls.add(key)

                    score = _fuzzy_score(keyword, album.display_name)
                    if score < 0.45:
                        continue
                    matches.append(
                        SearchHit(
                            album=album,
                            scraper=scraper,
                            source_name=source_name,
                            score=score,
                        )
                    )

        matches.sort(
            key=lambda item: (item.score, item.album.year or 0, item.album.display_name.lower()),
            reverse=True,
        )
        return matches

    def _search_flow(self) -> None:
        """Search album names across all sources and download selected results."""
        _rule("  Search Albums  ")
        keyword = _ask("Enter movie / album keyword [0=back]", default="").strip()
        if not keyword or _is_back_choice(keyword):
            return

        pages_str = _ask("Search depth: pages per source [1-5]", default="2")
        try:
            max_pages = max(1, min(5, int(pages_str)))
        except ValueError:
            max_pages = 2

        results: List[SearchHit] = []
        with Status(
            "[bold cyan]  Searching albums across sources...[/]",
            spinner="dots",
            console=console,
        ):
            results = self._collect_search_hits(keyword, max_pages=max_pages)

        if not results:
            console.print("[yellow]  No matching albums found. Try another keyword.[/]")
            return

        while True:
            console.print()
            _rule(f"  Search Results: {keyword}  ")
            _show_search_table(results)

            raw = _ask(
                f"Select result(s)  [dim]1...{len(results)}  1,3  2-5  all  0=back[/]",
                default="0",
            )
            if _is_back_choice(raw):
                return

            selected = _parse_selection(raw, results)
            if not selected:
                console.print("[yellow]  No valid selection.[/]")
                continue

            for hit in selected:
                self.scraper = hit.scraper
                self._download_album_flow(hit.album)

            if not _yn("\n  Download another from search results?"):
                return

    # â”€â”€ album download flow â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _download_album_flow(self, album: Album) -> None:
        console.print()
        console.print(
            Panel(
                Text.assemble(
                    ("ðŸ“€  ", "yellow"),
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
            "[bold cyan]  Fetching track listâ€¦[/]",
            spinner="dots",
            console=console,
        ):
            try:
                songs = self.scraper.get_songs(album)
            except Exception:
                logger.exception("Song fetch error for album=%s", album.display_name)

        if not songs:
            console.print("[red]  âŒ  No songs found for this album.[/]")
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

        # Attach download path + ID3 metadata context for downloader tagging.
        mp3_track_no = 0
        for s in to_download:
            s.album_name = album.safe_dirname
            s.album_title = album.display_name
            s.year = album.year
            if not s.artist:
                s.artist = "Unknown Artist"
            if s.is_zip:
                s.track_number = None
                continue
            mp3_track_no += 1
            s.track_number = mp3_track_no

        console.print()
        _rule(f"  Downloading: {album.display_name}  ")

        self._refresh_downloader_from_settings()
        if settings.concurrent_enabled:
            results = self.downloader.download_concurrent(
                to_download,
                album_name=album.safe_dirname,
                max_workers=settings.get("download.max_workers", 3),
            )
        else:
            console.print("  [dim]Concurrent downloads disabled. Using sequential mode.[/]")
            results = self.downloader.download_songs(to_download)

        ok  = sum(1 for r in results if r.success)
        err = len(results) - ok
        size_total = sum(r.size_downloaded for r in results if r.size_downloaded)
        size_mb = size_total / (1024 * 1024)

        console.print()
        _rule()
        console.print(
            f"  [bold]Done![/]  "
            f"[green]âœ“ {ok} downloaded[/]"
            + (f"   [red]âœ— {err} failed[/]" if err else "")
            + f"   [yellow]{size_mb:.1f} MB[/]"
        )
        console.print(f"  [dim]Saved to:  {settings.output_dir / 'IsaiminiHQ' / album.safe_dirname}[/]")

        # Show failures if any
        if err:
            for r in results:
                if not r.success:
                    console.print(f"    [red]âœ—[/] {r.song_name}  [dim]{r.error_message}[/]")

    # â”€â”€ settings menu â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

    def _print_settings_summary(self) -> None:
        """Render current persisted settings for download behavior."""
        console.print(
            f"  [dim]Output directory      :[/]  {settings.output_dir}\n"
            f"  [dim]Concurrent downloads  :[/]  {'ON' if settings.concurrent_enabled else 'OFF'}\n"
            f"  [dim]Max workers           :[/]  {settings.get('download.max_workers', 3)}\n"
            f"  [dim]Progress bars         :[/]  {'ON' if settings.show_progress else 'OFF'}\n"
        )

    def _change_output_directory(self) -> None:
        new_output = _ask("New output directory", default=str(settings.output_dir)).strip()
        if not new_output:
            console.print("  [yellow]Output directory unchanged.[/]")
            return

        new_path = Path(new_output).expanduser()
        settings.set("download.output_dir", str(new_path))
        self._refresh_downloader_from_settings()
        console.print(f"  [green]Output directory set to: {settings.output_dir}[/]")

    def _toggle_concurrent_downloads(self) -> None:
        new_value = not settings.concurrent_enabled
        settings.set("download.concurrent_enabled", new_value)
        console.print(
            "  [green]Concurrent downloads "
            + ("enabled.[/]" if new_value else "disabled.[/]")
        )

    def _set_max_workers(self) -> None:
        current = str(settings.get("download.max_workers", 3))
        raw_workers = _ask("Workers (1-8)", default=current).strip()
        try:
            workers = max(1, min(8, int(raw_workers)))
        except ValueError:
            console.print("  [yellow]Invalid number. Max workers unchanged.[/]")
            return

        settings.set("download.max_workers", workers)
        self._refresh_downloader_from_settings()
        console.print(f"  [green]Max workers set to {workers}.[/]")

    def _toggle_progress_bar(self) -> None:
        new_value = not settings.show_progress
        settings.set("ui.show_progress", new_value)
        self._refresh_downloader_from_settings()
        console.print(
            "  [green]Progress bars "
            + ("enabled.[/]" if new_value else "disabled.[/]")
        )

    def _settings_menu(self) -> None:
        handlers: Dict[str, Callable[[], None]] = {
            "1": self._change_output_directory,
            "2": self._toggle_concurrent_downloads,
            "3": self._set_max_workers,
            "4": self._toggle_progress_bar,
        }

        while True:
            _rule("  Settings  ")
            self._print_settings_summary()
            console.print(
                "  [cyan]1[/]  Change output directory\n"
                "  [cyan]2[/]  Toggle concurrent downloads\n"
                "  [cyan]3[/]  Set max workers\n"
                "  [cyan]4[/]  Toggle progress bar\n"
                "  [cyan]0[/]  Back\n"
            )

            choice = _ask("Choose setting", choices=["0", "1", "2", "3", "4"], default="0")
            if choice == "0":
                return
            handlers[choice]()


# â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def main() -> None:
    app: Optional[TamilMP3Downloader] = None
    try:
        app = TamilMP3Downloader()
        app.run()
    except KeyboardInterrupt:
        console.print("\n[green]ðŸ‘‹  Goodbye![/]\n")
        sys.exit(0)
    except Exception:
        logger.exception("Fatal error in main loop.")
        console.print_exception()
        sys.exit(1)
    finally:
        # Always close playwright browser
        if app is not None:
            try:
                app.scraper._close_browser()
            except Exception:
                logger.debug("Failed to close scraper browser cleanly.", exc_info=True)


if __name__ == "__main__":
    main()

