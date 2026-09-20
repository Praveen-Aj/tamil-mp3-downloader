"""
Composable Filter Engine for Tamil Music Downloader.

Implements the Specification Pattern to build dynamic, parameterized SQL queries
combining FTS5 full-text search, multi-field metadata filters, multi-column sorting,
and pagination over the canonical SQLite database.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Tuple, Any, Dict
from library.models import SongState


@dataclass
class SongFilterCriteria:
    """
    Search and filter criteria specification for music library queries.
    """
    search_query: Optional[str] = None
    download_state: Optional[SongState] = None
    quality_kbps: Optional[int] = None
    source_name: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    year: Optional[int] = None
    min_rating: Optional[int] = None
    is_favorite: Optional[bool] = None
    formats: List[str] = field(default_factory=list)

    @classmethod
    def from_legacy_params(
        cls,
        query: str = "",
        state_filter: Optional[str] = None,
        quality: Optional[int] = None,
        source: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
    ) -> 'SongFilterCriteria':
        """Construct criteria from legacy or view parameter strings."""
        parsed_state: Optional[SongState] = None
        if state_filter:
            s_upper = state_filter.upper().strip()
            if s_upper in ("OWNED", "DOWNLOADED"):
                parsed_state = SongState.OWNED
            elif s_upper in ("NEW", "NOT DOWNLOADED", "UNOWNED"):
                parsed_state = SongState.NEW
            elif s_upper in SongState.__members__:
                parsed_state = SongState[s_upper]

        return cls(
            search_query=query.strip() if query and query.strip() else None,
            download_state=parsed_state,
            quality_kbps=quality,
            source_name=source.strip() if source and source.strip() and source.upper() != "ALL" else None,
            artist=artist.strip() if artist and artist.strip() and artist.upper() != "ALL" else None,
            album=album.strip() if album and album.strip() and album.upper() != "ALL" else None,
        )


class ComposableFilterEngine:
    """
    Builds optimized, injection-safe SQL queries from SongFilterCriteria.
    """

    ALLOWED_SORT_COLUMNS: Dict[str, str] = {
        "title": "s.title_normalized",
        "artist": "s.artist_normalized",
        "album": "s.album_normalized",
        "quality": "s.quality_kbps",
        "state": "s.state",
        "year": "s.year",
        "date_added": "s.first_discovered_at",
        "last_seen": "s.last_seen_at",
        "id": "s.id",
        "rank": "songs_fts.rank",
    }

    @staticmethod
    def sanitize_fts_query(query: str) -> Optional[str]:
        """
        Sanitize user query into safe FTS5 prefix match tokens.
        Example: 'vaathi coming 2026' -> '"vaathi"* "coming"* "2026"*'
        """
        if not query or not query.strip():
            return None
        # Extract alphanumeric or unicode words
        tokens = re.findall(r'[\w]+', query, re.UNICODE)
        if not tokens:
            return None
        # Format as prefix tokens
        return " ".join(f'"{t}"*' for t in tokens)

    def build_query(
        self,
        criteria: SongFilterCriteria,
        sort_by: str = "id",
        ascending: bool = False,
        page: int = 1,
        page_size: int = 50,
        use_fts: bool = True,
    ) -> Tuple[str, List[Any], str, List[Any]]:
        """
        Generate parameterized count SQL and paginated select SQL.

        Args:
            criteria: Search and filter criteria
            sort_by: Field name to sort by
            ascending: Sort direction
            page: 1-indexed page number
            page_size: Maximum records per page
            use_fts: Whether to utilize songs_fts virtual table for text search

        Returns:
            Tuple of (count_sql, count_params, data_sql, data_params)
        """
        joins: List[str] = []
        where_clauses: List[str] = ["1=1"]
        params: List[Any] = []

        is_fts_active = False
        if criteria.search_query:
            fts_expr = self.sanitize_fts_query(criteria.search_query) if use_fts else None
            if fts_expr:
                joins.append("JOIN songs_fts ON songs_fts.rowid = s.id")
                where_clauses.append("songs_fts MATCH ?")
                params.append(fts_expr)
                is_fts_active = True
            else:
                # Fallback to LIKE matching
                pattern = f"%{criteria.search_query.strip()}%"
                where_clauses.append("(s.title LIKE ? OR s.artist LIKE ? OR s.album LIKE ?)")
                params.extend([pattern, pattern, pattern])

        # State filter
        if criteria.download_state:
            where_clauses.append("s.state = ?")
            params.append(criteria.download_state.value)

        # Quality filter
        if criteria.quality_kbps is not None:
            where_clauses.append("s.quality_kbps >= ?")
            params.append(criteria.quality_kbps)

        # Source / Provider filter
        if criteria.source_name:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM song_sources src WHERE src.song_id = s.id AND src.source_name = ?)"
            )
            params.append(criteria.source_name)

        # Artist filter
        if criteria.artist:
            norm_art = criteria.artist.lower().strip()
            where_clauses.append("(s.artist_normalized = ? OR s.artist LIKE ?)")
            params.extend([norm_art, f"%{criteria.artist}%"])

        # Album filter
        if criteria.album:
            norm_alb = criteria.album.lower().strip()
            where_clauses.append("(s.album_normalized = ? OR s.album LIKE ?)")
            params.extend([norm_alb, f"%{criteria.album}%"])

        # Year filter
        if criteria.year:
            where_clauses.append("s.year = ?")
            params.append(criteria.year)

        # Rating filter
        if criteria.min_rating is not None:
            where_clauses.append(
                "EXISTS (SELECT 1 FROM user_song_metadata m WHERE m.song_id = s.id AND m.rating >= ?)"
            )
            params.append(criteria.min_rating)

        # Favorite filter
        if criteria.is_favorite is not None:
            val = 1 if criteria.is_favorite else 0
            where_clauses.append(
                "EXISTS (SELECT 1 FROM user_song_metadata m WHERE m.song_id = s.id AND m.is_favorite = ?)"
            )
            params.append(val)

        # Formats filter
        if criteria.formats:
            fmt_clauses = ["s.file_path LIKE ?" for _ in criteria.formats]
            where_clauses.append(f"({' OR '.join(fmt_clauses)})")
            for fmt in criteria.formats:
                params.append(f"%.{fmt.lower().strip('.')}")

        # Assemble FROM and WHERE
        from_clause = "FROM songs s"
        if joins:
            from_clause += " " + " ".join(joins)

        where_clause = "WHERE " + " AND ".join(where_clauses)

        # Count query
        count_sql = f"SELECT COUNT(*) {from_clause} {where_clause}"
        count_params = list(params)

        # Sorting
        sort_col = self.ALLOWED_SORT_COLUMNS.get(sort_by.lower(), "s.id")
        # If FTS is active and sort is rank, order by f.rank ASC (smaller rank is better match)
        if is_fts_active and sort_by.lower() == "rank":
            order_expr = f"songs_fts.rank {'ASC' if ascending else 'ASC'}"
        else:
            dir_str = "ASC" if ascending else "DESC"
            order_expr = f"{sort_col} {dir_str}"
            if sort_col != "s.id":
                order_expr += ", s.id DESC"

        # Pagination offsets
        effective_page = max(1, page)
        effective_limit = max(1, page_size)
        offset = (effective_page - 1) * effective_limit

        data_sql = f"SELECT s.* {from_clause} {where_clause} ORDER BY {order_expr} LIMIT ? OFFSET ?"
        data_params = list(params) + [effective_limit, offset]

        return count_sql, count_params, data_sql, data_params
