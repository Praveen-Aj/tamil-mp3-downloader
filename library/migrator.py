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
    CURRENT_VERSION = 1

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
            # Get all table names
            cursor = self.db._conn.cursor()
            cursor.execute("""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name NOT LIKE 'sqlite_%'
            """)
            tables = [row[0] for row in cursor.fetchall()]

            # Drop all tables
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"Dropped table: {table}")

            # Reapply initial schema
            self._apply_migration(1)

        logger.info("Database reset complete")
