"""
Database migration system for the library.

Handles schema versioning and incremental migrations to support
database schema evolution over time.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from library.database import SQLiteDatabase

logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """
    Database migration manager.

    Handles schema version tracking and executes migrations
    to bring the database up to the current version.
    """

    # Current schema version
    CURRENT_VERSION = 4

    # Migration definitions
    MIGRATIONS = {
        1: """
        -- Initial schema
        -- Library locations (configurable music directories)
        CREATE TABLE IF NOT EXISTS library_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            is_primary BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_scanned_at TIMESTAMP
        );

        -- Canonical songs (normalized identity)
        CREATE TABLE IF NOT EXISTS songs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            canonical_hash TEXT NOT NULL UNIQUE,
            title_normalized TEXT NOT NULL,
            artist_normalized TEXT NOT NULL,
            album_normalized TEXT NOT NULL,
            year INTEGER,
            duration_seconds INTEGER,
            
            -- Original display values (for UI)
            title TEXT NOT NULL,
            artist TEXT,
            album TEXT,
            
            -- Library state
            state TEXT NOT NULL DEFAULT 'NEW',
            quality_kbps INTEGER,
            file_size_bytes INTEGER,
            
            -- Primary file location
            library_location_id INTEGER,
            file_path TEXT,
            
            -- Metadata
            first_discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_played_at TIMESTAMP,
            play_count INTEGER DEFAULT 0,
            
            FOREIGN KEY (library_location_id) REFERENCES library_locations(id)
        );

        CREATE INDEX IF NOT EXISTS idx_songs_canonical_hash ON songs(canonical_hash);
        CREATE INDEX IF NOT EXISTS idx_songs_state ON songs(state);
        CREATE INDEX IF NOT EXISTS idx_songs_title_artist ON songs(title_normalized, artist_normalized);
        CREATE INDEX IF NOT EXISTS idx_songs_library_location ON songs(library_location_id);

        -- Source variants (multiple sources per canonical song)
        CREATE TABLE IF NOT EXISTS song_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            source_name TEXT NOT NULL,
            source_url TEXT NOT NULL,
            quality_kbps INTEGER,
            file_size_bytes INTEGER,
            file_type TEXT,
            metadata_complete BOOLEAN DEFAULT 0,
            is_available BOOLEAN DEFAULT 1,
            availability_last_checked TIMESTAMP,
            reliability_score REAL DEFAULT 1.0,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            UNIQUE(song_id, source_url)
        );

        CREATE INDEX IF NOT EXISTS idx_song_sources_song_id ON song_sources(song_id);
        CREATE INDEX IF NOT EXISTS idx_song_sources_source ON song_sources(source_name);
        CREATE INDEX IF NOT EXISTS idx_song_sources_quality ON song_sources(quality_kbps);

        -- Download history
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            song_source_id INTEGER NOT NULL,
            
            -- Planning
            planned_at TIMESTAMP,
            queued_at TIMESTAMP,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            failed_at TIMESTAMP,
            
            -- Execution
            library_location_id INTEGER,
            output_path TEXT,
            file_size_bytes INTEGER,
            download_speed_bps REAL,
            
            -- Outcome
            state TEXT NOT NULL,
            error_message TEXT,
            retry_count INTEGER DEFAULT 0,
            
            -- Quality upgrade info
            was_upgrade BOOLEAN DEFAULT 0,
            previous_file_path TEXT,
            previous_quality_kbps INTEGER,
            
            FOREIGN KEY (song_id) REFERENCES songs(id),
            FOREIGN KEY (song_source_id) REFERENCES song_sources(id),
            FOREIGN KEY (library_location_id) REFERENCES library_locations(id)
        );

        CREATE INDEX IF NOT EXISTS idx_downloads_song_id ON downloads(song_id);
        CREATE INDEX IF NOT EXISTS idx_downloads_state ON downloads(state);
        CREATE INDEX IF NOT EXISTS idx_downloads_planned_at ON downloads(planned_at);

        -- Discovery context (which category/album songs came from)
        CREATE TABLE IF NOT EXISTS discovery_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            source_name TEXT NOT NULL,
            category TEXT,
            album_name TEXT,
            album_url TEXT,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_discovery_context_song_id ON discovery_context(song_id);

        -- Schema version for migrations
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        2: """
        -- Add download_reference to song_sources
        ALTER TABLE song_sources ADD COLUMN download_reference TEXT;
        """,
        3: """
        -- Import jobs and persistent playlist items
        CREATE TABLE IF NOT EXISTS import_jobs (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            platform TEXT NOT NULL,
            content_type TEXT NOT NULL,
            title TEXT NOT NULL,
            artist TEXT,
            total_tracks INTEGER DEFAULT 0,
            artwork_url TEXT,
            status TEXT NOT NULL DEFAULT 'READY',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS import_job_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id TEXT NOT NULL,
            track_index INTEGER NOT NULL,
            title TEXT NOT NULL,
            artist TEXT,
            album TEXT,
            duration_seconds INTEGER,
            state TEXT NOT NULL DEFAULT 'READY',
            selected_provider TEXT,
            selected_source_url TEXT,
            match_confidence REAL DEFAULT 0.0,
            match_explanation TEXT,
            error_message TEXT,
            download_id INTEGER,
            canonical_song_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (job_id) REFERENCES import_jobs(id) ON DELETE CASCADE,
            FOREIGN KEY (download_id) REFERENCES downloads(id),
            FOREIGN KEY (canonical_song_id) REFERENCES songs(id)
        );

        CREATE INDEX IF NOT EXISTS idx_import_job_items_job_id ON import_job_items(job_id);
        CREATE INDEX IF NOT EXISTS idx_import_job_items_state ON import_job_items(state);
        """,
        4: """
        -- Migration 4: V5.1 Multi-Dimensional Music Discovery & Library Foundation
        -- 1. Movies Catalog
        CREATE TABLE IF NOT EXISTS movies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL UNIQUE,
            title_normalized TEXT NOT NULL,
            year INTEGER,
            director TEXT,
            poster_url TEXT,
            banner_url TEXT,
            local_poster_path TEXT,
            track_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_movies_title_normalized ON movies(title_normalized);
        CREATE INDEX IF NOT EXISTS idx_movies_year ON movies(year);

        -- 2. Artists & Personnel Directory (Singers, Composers, Lyricists, Actors)
        CREATE TABLE IF NOT EXISTS artists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            name_normalized TEXT NOT NULL,
            role TEXT DEFAULT 'artist',
            photo_url TEXT,
            local_photo_path TEXT,
            bio TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_artists_name_normalized ON artists(name_normalized);
        CREATE INDEX IF NOT EXISTS idx_artists_role ON artists(role);

        -- 3. Movie Actors Join Table
        CREATE TABLE IF NOT EXISTS movie_actors (
            movie_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,
            character_name TEXT,
            PRIMARY KEY (movie_id, actor_id),
            FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
            FOREIGN KEY (actor_id) REFERENCES artists(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_movie_actors_actor ON movie_actors(actor_id);

        -- 4. Movie Composers / Music Directors Join Table
        CREATE TABLE IF NOT EXISTS movie_composers (
            movie_id INTEGER NOT NULL,
            composer_id INTEGER NOT NULL,
            PRIMARY KEY (movie_id, composer_id),
            FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
            FOREIGN KEY (composer_id) REFERENCES artists(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_movie_composers_composer ON movie_composers(composer_id);

        -- 5. Canonical Song Artists / Credits Join Table
        CREATE TABLE IF NOT EXISTS song_artists (
            song_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            role TEXT DEFAULT 'singer',
            PRIMARY KEY (song_id, artist_id, role),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_song_artists_artist ON song_artists(artist_id);
        CREATE INDEX IF NOT EXISTS idx_song_artists_role ON song_artists(role);

        -- 6. Canonical Song Movies Join Table (M:N mapping)
        CREATE TABLE IF NOT EXISTS song_movies (
            song_id INTEGER NOT NULL,
            movie_id INTEGER NOT NULL,
            track_number INTEGER,
            PRIMARY KEY (song_id, movie_id),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_song_movies_movie ON song_movies(movie_id);

        -- 7. User Song Metadata (Ratings, Favorites, Personal Notes & Tags)
        CREATE TABLE IF NOT EXISTS user_song_metadata (
            song_id INTEGER PRIMARY KEY,
            rating INTEGER CHECK (rating IS NULL OR (rating >= 1 AND rating <= 5)),
            is_favorite BOOLEAN DEFAULT 0,
            notes TEXT,
            tags TEXT,
            favorited_at TIMESTAMP,
            last_rated_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
        );

        CREATE INDEX IF NOT EXISTS idx_user_meta_rating ON user_song_metadata(rating);
        CREATE INDEX IF NOT EXISTS idx_user_meta_favorite ON user_song_metadata(is_favorite);

        -- 8. User Playlists
        CREATE TABLE IF NOT EXISTS playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            cover_url TEXT,
            is_smart BOOLEAN DEFAULT 0,
            smart_criteria_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_playlists_name ON playlists(name);

        -- 9. Playlist Items (Referencing Canonical Songs)
        CREATE TABLE IF NOT EXISTS playlist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            song_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            UNIQUE (playlist_id, song_id)
        );

        CREATE INDEX IF NOT EXISTS idx_playlist_items_playlist ON playlist_items(playlist_id);
        CREATE INDEX IF NOT EXISTS idx_playlist_items_song ON playlist_items(song_id);
        CREATE INDEX IF NOT EXISTS idx_playlist_items_pos ON playlist_items(playlist_id, position);

        -- 10. Curated Charts & Snapshots
        CREATE TABLE IF NOT EXISTS charts (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            chart_type TEXT NOT NULL,
            provider_name TEXT NOT NULL,
            snapshot_date TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_charts_type ON charts(chart_type);
        CREATE INDEX IF NOT EXISTS idx_charts_snapshot ON charts(snapshot_date);

        -- 11. Ranked Chart Entries
        CREATE TABLE IF NOT EXISTS chart_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chart_id TEXT NOT NULL,
            rank INTEGER NOT NULL,
            previous_rank INTEGER,
            song_id INTEGER,
            raw_title TEXT NOT NULL,
            raw_artist TEXT,
            raw_movie TEXT,
            FOREIGN KEY (chart_id) REFERENCES charts(id) ON DELETE CASCADE,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE SET NULL,
            UNIQUE (chart_id, rank)
        );

        CREATE INDEX IF NOT EXISTS idx_chart_entries_chart ON chart_entries(chart_id);
        CREATE INDEX IF NOT EXISTS idx_chart_entries_song ON chart_entries(song_id);
        CREATE INDEX IF NOT EXISTS idx_chart_entries_rank ON chart_entries(chart_id, rank);
        """
    }

    def __init__(self, db: 'SQLiteDatabase'):
        """
        Initialize migrator.

        Args:
            db: SQLiteDatabase instance
        """
        self.db = db

    def migrate(self) -> None:
        """
        Run migrations to bring database to current version.

        This method:
        1. Checks current schema version
        2. Executes any pending migrations
        3. Updates schema version
        """
        if not self.db._conn:
            raise RuntimeError("Database not connected")

        current_version = self._get_current_version()
        logger.info(f"Current schema version: {current_version}")

        if current_version == self.CURRENT_VERSION:
            logger.info("Database is up to date")
            return

        if current_version > self.CURRENT_VERSION:
            logger.warning(
                f"Database version {current_version} is newer than expected {self.CURRENT_VERSION}. "
                "This may indicate a downgrade."
            )
            return

        # Run migrations from current_version + 1 to CURRENT_VERSION
        for version in range(current_version + 1, self.CURRENT_VERSION + 1):
            self._apply_migration(version)

        logger.info(f"Database migrated to version {self.CURRENT_VERSION}")

    def _get_current_version(self) -> int:
        """
        Get current schema version from database.

        Returns:
            Current schema version (0 if no version table exists)
        """
        cursor = self.db._conn.cursor()

        # Check if schema_version table exists
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='schema_version'
        """)
        if not cursor.fetchone():
            return 0

        # Get current version
        cursor.execute("SELECT MAX(version) FROM schema_version")
        result = cursor.fetchone()
        return result[0] if result[0] else 0

    def _apply_migration(self, version: int) -> None:
        """
        Apply a specific migration.

        Args:
            version: Migration version to apply
        """
        if version not in self.MIGRATIONS:
            raise ValueError(f"No migration defined for version {version}")

        migration_sql = self.MIGRATIONS[version]
        logger.info(f"Applying migration {version}")

        try:
            # Execute migration in a transaction
            with self.db._conn:
                # Split migration into individual statements
                statements = [s.strip() for s in migration_sql.split(';') if s.strip()]
                for statement in statements:
                    if statement:
                        self.db._conn.execute(statement)

                # Record migration
                self.db._conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (version,)
                )

            logger.info(f"Migration {version} applied successfully")
        except Exception as e:
            logger.error(f"Migration {version} failed: {e}")
            raise

    def reset_database(self) -> None:
        """
        Reset database by dropping all tables and reapplying schema.

        WARNING: This will delete all data. Use only for testing.
        """
        logger.warning("Resetting database - all data will be lost")

        if not self.db._conn:
            raise RuntimeError("Database not connected")

        with self.db._conn:
            cursor = self.db._conn.cursor()
            cursor.execute("PRAGMA foreign_keys = OFF")
            # Get all table names
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            # Drop all tables
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"Dropped table: {table}")

            cursor.execute("PRAGMA foreign_keys = ON")

            # Reapply all migrations up to current version
            for version in range(1, self.CURRENT_VERSION + 1):
                self._apply_migration(version)

        logger.info("Database reset complete")
