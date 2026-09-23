CREATE INDEX idx_artists_name_normalized ON artists(name_normalized);

CREATE INDEX idx_artists_role ON artists(role);

CREATE INDEX idx_chart_entries_chart ON chart_entries(chart_id);

CREATE INDEX idx_chart_entries_rank ON chart_entries(chart_id, rank);

CREATE INDEX idx_chart_entries_song ON chart_entries(song_id);

CREATE INDEX idx_charts_snapshot ON charts(snapshot_date);

CREATE INDEX idx_charts_type ON charts(chart_type);

CREATE INDEX idx_discovery_context_song_id ON discovery_context(song_id);

CREATE INDEX idx_downloads_planned_at ON downloads(planned_at);

CREATE INDEX idx_downloads_song_id ON downloads(song_id);

CREATE INDEX idx_downloads_state ON downloads(state);

CREATE INDEX idx_import_job_items_job_id ON import_job_items(job_id);

CREATE INDEX idx_import_job_items_state ON import_job_items(state);

CREATE INDEX idx_movie_actors_actor ON movie_actors(actor_id);

CREATE INDEX idx_movie_composers_composer ON movie_composers(composer_id);

CREATE INDEX idx_movies_title_normalized ON movies(title_normalized);

CREATE INDEX idx_movies_year ON movies(year);

CREATE INDEX idx_playlist_items_playlist ON playlist_items(playlist_id);

CREATE INDEX idx_playlist_items_pos ON playlist_items(playlist_id, position);

CREATE INDEX idx_playlist_items_song ON playlist_items(song_id);

CREATE INDEX idx_playlists_name ON playlists(name);

CREATE INDEX idx_song_artists_artist ON song_artists(artist_id);

CREATE INDEX idx_song_artists_role ON song_artists(role);

CREATE INDEX idx_song_movies_movie ON song_movies(movie_id);

CREATE INDEX idx_song_sources_quality ON song_sources(quality_kbps);

CREATE INDEX idx_song_sources_song_id ON song_sources(song_id);

CREATE INDEX idx_song_sources_source ON song_sources(source_name);

CREATE INDEX idx_songs_canonical_hash ON songs(canonical_hash);

CREATE INDEX idx_songs_library_location ON songs(library_location_id);

CREATE INDEX idx_songs_quality ON songs(quality_kbps);

CREATE INDEX idx_songs_state ON songs(state);

CREATE INDEX idx_songs_title ON songs(title_normalized);

CREATE INDEX idx_songs_title_artist ON songs(title_normalized, artist_normalized);

CREATE INDEX idx_songs_year ON songs(year);

CREATE INDEX idx_user_meta_favorite ON user_song_metadata(is_favorite);

CREATE INDEX idx_user_meta_rating ON user_song_metadata(rating);

CREATE TABLE artists (
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

CREATE TABLE chart_entries (
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

CREATE TABLE charts (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            chart_type TEXT NOT NULL,
            provider_name TEXT NOT NULL,
            snapshot_date TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE discovery_context (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            song_id INTEGER NOT NULL,
            source_name TEXT NOT NULL,
            category TEXT,
            album_name TEXT,
            album_url TEXT,
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE
        );

CREATE TABLE downloads (
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

CREATE TABLE import_job_items (
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

CREATE TABLE import_jobs (
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

CREATE TABLE library_locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL UNIQUE,
            name TEXT NOT NULL,
            is_primary BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_scanned_at TIMESTAMP
        );

CREATE TABLE movie_actors (
            movie_id INTEGER NOT NULL,
            actor_id INTEGER NOT NULL,
            character_name TEXT,
            PRIMARY KEY (movie_id, actor_id),
            FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
            FOREIGN KEY (actor_id) REFERENCES artists(id) ON DELETE CASCADE
        );

CREATE TABLE movie_composers (
            movie_id INTEGER NOT NULL,
            composer_id INTEGER NOT NULL,
            PRIMARY KEY (movie_id, composer_id),
            FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE,
            FOREIGN KEY (composer_id) REFERENCES artists(id) ON DELETE CASCADE
        );

CREATE TABLE movies (
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

CREATE TABLE playlist_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            playlist_id INTEGER NOT NULL,
            song_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            UNIQUE (playlist_id, song_id)
        );

CREATE TABLE playlists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            cover_url TEXT,
            is_smart BOOLEAN DEFAULT 0,
            smart_criteria_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

CREATE TABLE song_artists (
            song_id INTEGER NOT NULL,
            artist_id INTEGER NOT NULL,
            role TEXT DEFAULT 'singer',
            PRIMARY KEY (song_id, artist_id, role),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            FOREIGN KEY (artist_id) REFERENCES artists(id) ON DELETE CASCADE
        );

CREATE TABLE song_movies (
            song_id INTEGER NOT NULL,
            movie_id INTEGER NOT NULL,
            track_number INTEGER,
            PRIMARY KEY (song_id, movie_id),
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            FOREIGN KEY (movie_id) REFERENCES movies(id) ON DELETE CASCADE
        );

CREATE TABLE song_sources (
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
            discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, download_reference TEXT,
            
            FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
            UNIQUE(song_id, source_url)
        );

CREATE TABLE songs (
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

CREATE VIRTUAL TABLE songs_fts USING fts5(
            title,
            artist,
            album,
            content='songs',
            content_rowid='id',
            tokenize='unicode61 remove_diacritics 2'
        );

CREATE TABLE 'songs_fts_config'(k PRIMARY KEY, v) WITHOUT ROWID;

CREATE TABLE 'songs_fts_data'(id INTEGER PRIMARY KEY, block BLOB);

CREATE TABLE 'songs_fts_docsize'(id INTEGER PRIMARY KEY, sz BLOB);

CREATE TABLE 'songs_fts_idx'(segid, term, pgno, PRIMARY KEY(segid, term)) WITHOUT ROWID;

CREATE TABLE sqlite_sequence(name,seq);

CREATE TABLE user_song_metadata (
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

CREATE TRIGGER songs_ad AFTER DELETE ON songs BEGIN
            INSERT INTO songs_fts(songs_fts, rowid, title, artist, album)
            VALUES ('delete', old.id, old.title, coalesce(old.artist, ''), coalesce(old.album, ''));
        END;

CREATE TRIGGER songs_ai AFTER INSERT ON songs BEGIN
            INSERT INTO songs_fts(rowid, title, artist, album)
            VALUES (new.id, new.title, coalesce(new.artist, ''), coalesce(new.album, ''));
        END;

CREATE TRIGGER songs_au AFTER UPDATE ON songs BEGIN
            INSERT INTO songs_fts(songs_fts, rowid, title, artist, album)
            VALUES ('delete', old.id, old.title, coalesce(old.artist, ''), coalesce(old.album, ''));
            INSERT INTO songs_fts(rowid, title, artist, album)
            VALUES (new.id, new.title, coalesce(new.artist, ''), coalesce(new.album, ''));
        END;