# Global Music Library & Download Planning Architecture

Redesign Tamil MP3 Downloader with SQLite-based global library index, canonical song identity system, cross-category/source deduplication, and intelligent download planning.

## Executive Summary

This plan redesigns the Tamil MP3 Downloader around a persistent global music library using SQLite. The system introduces canonical song identity, cross-category/source deduplication, intelligent download planning, and quality-aware upgrades while maintaining the existing pluggable scraper architecture.

## Current Architecture Analysis

### Existing Components

**Scrapers** (pluggable via BaseScraper):
- `IsaiminiScraper` - Playwright-based, supports multiple categories
- `MassTamilanScraper` - cloudscraper + Playwright fallback
- `FriendsTamilMP3Scraper` - HTTP-based, supports stars/singers/MD categories
- `KollySongsScraper` - (referenced but not fully inspected)

**Models**:
- `Song` - name, url, size_mb, quality, album_name, artist, album_title, year, track_number, cover_art
- `Album` - name, url, year, song_count, source
- `DownloadResult` - success, song_name, file_path, error_message, size_downloaded

**Downloader**:
- `HTTPDownloader` - concurrent/sequential downloads, resume support, ID3 tagging, aria2 integration
- Uses `.part` files and `.download_state.json` for resume
- Quality preference (320kbps over 128kbps)

**Current Deduplication**:
- `_dedup_songs()` - simple name-based dedup with "first" or "smaller-size" strategy
- `_find_existing_in_dir()` - filename-based skip check in download folder
- **No cross-category deduplication**
- **No cross-source deduplication**
- **No persistent library state**

**Cache**:
- JSON-based cache in `cache/` directory
- Per-source/category/album caching
- TTL-based expiration
- **No library metadata persistence**

**Concurrency**:
- ThreadPoolExecutor for concurrent downloads
- Fallback to sequential on failure
- **No central download registry**
- **Duplicate prevention only via file existence check**

### Gaps vs Requirements

| Requirement | Current State | Gap |
|-------------|---------------|-----|
| Persistent global library index | None (JSON cache only) | **Critical** |
| Canonical song identity | Simple filename normalization | **Critical** |
| Cross-category deduplication | None | **Critical** |
| Cross-source deduplication | None | **Critical** |
| Download planning | None (direct download) | **Critical** |
| Library state tracking | None | **Critical** |
| Concurrent duplicate prevention | File existence only | **Critical** |
| Quality upgrades | None | **Important** |
| Library import | None | **Important** |
| SQLite database | None | **Critical** |

## Database Schema Design

### Location
- **OS user data directory**: `%APPDATA%/tamil-mp3-downloader/` on Windows, `~/.local/share/tamil-mp3-downloader/` on Linux
- Database file: `library.db`
- Schema versioned for migrations

### Tables

```sql
-- Library locations (configurable music directories)
CREATE TABLE library_locations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    is_primary BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_scanned_at TIMESTAMP
);

-- Canonical songs (normalized identity)
CREATE TABLE songs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_hash TEXT NOT NULL UNIQUE,  -- SHA256 of normalized metadata
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
    state TEXT NOT NULL DEFAULT 'NEW',  -- NEW, OWNED, QUEUED, DOWNLOADING, COMPLETED, FAILED, MISSING, DUPLICATE
    quality_kbps INTEGER,  -- Best quality available
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

CREATE INDEX idx_songs_canonical_hash ON songs(canonical_hash);
CREATE INDEX idx_songs_state ON songs(state);
CREATE INDEX idx_songs_title_artist ON songs(title_normalized, artist_normalized);
CREATE INDEX idx_songs_library_location ON songs(library_location_id);

-- Source variants (multiple sources per canonical song)
CREATE TABLE song_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    song_id INTEGER NOT NULL,
    source_name TEXT NOT NULL,  -- isaimini, masstamilan, friendstamilmp3, kollysongs
    source_url TEXT NOT NULL,
    quality_kbps INTEGER,
    file_size_bytes INTEGER,
    file_type TEXT,  -- mp3, zip, m4a, etc.
    metadata_complete BOOLEAN DEFAULT 0,
    is_available BOOLEAN DEFAULT 1,
    availability_last_checked TIMESTAMP,
    reliability_score REAL DEFAULT 1.0,  -- 0.0-1.0 based on success rate
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (song_id) REFERENCES songs(id) ON DELETE CASCADE,
    UNIQUE(song_id, source_url)
);

CREATE INDEX idx_song_sources_song_id ON song_sources(song_id);
CREATE INDEX idx_song_sources_source ON song_sources(source_name);
CREATE INDEX idx_song_sources_quality ON song_sources(quality_kbps);

-- Download history
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
    state TEXT NOT NULL,  -- PLANNED, QUEUED, DOWNLOADING, COMPLETED, FAILED, CANCELLED
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

CREATE INDEX idx_downloads_song_id ON downloads(song_id);
CREATE INDEX idx_downloads_state ON downloads(state);
CREATE INDEX idx_downloads_planned_at ON downloads(planned_at);

-- Discovery context (which category/album songs came from)
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

CREATE INDEX idx_discovery_context_song_id ON discovery_context(song_id);

-- Schema version for migrations
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial version
INSERT INTO schema_version (version) VALUES (1);
```

## Canonical Identity System

### Canonical Hash Algorithm

```python
def compute_canonical_hash(title: str, artist: str, album: str, 
                          year: Optional[int], duration: Optional[int]) -> str:
    """
    Compute canonical hash for song identity.
    
    Normalization rules:
    - Strip: Remix, Instrumental, Karaoke, Extended, Reprise, Version
    - Case-insensitive
    - Remove extra whitespace and special chars
    - Normalize Tamil transliteration (future enhancement)
    """
    # Extract base title (remove variant suffixes)
    base_title = extract_base_title(title)
    
    # Normalize components
    norm_title = normalize_string(base_title)
    norm_artist = normalize_string(artist) if artist else ""
    norm_album = normalize_string(album) if album else ""
    
    # Create canonical string
    canonical_parts = [norm_title, norm_artist, norm_album]
    if year:
        canonical_parts.append(str(year))
    if duration:
        canonical_parts.append(str(duration))
    
    canonical_string = "|".join(canonical_parts)
    
    # SHA256 hash
    return hashlib.sha256(canonical_string.encode('utf-8')).hexdigest()

def extract_base_title(title: str) -> str:
    """Remove variant suffixes from title."""
    variant_suffixes = [
        r'\s*-\s*Remix$', r'\s*-\s*Instrumental$', r'\s*-\s*Karaoke$',
        r'\s*-\s*Extended$', r'\s*-\s*Reprise$', r'\s*-\s*Version\s*\d*$',
        r'\s*\(Remix\)$', r'\s*\(Instrumental\)$', r'\s*\(Karaoke\)$',
    ]
    base = title
    for suffix in variant_suffixes:
        base = re.sub(suffix, '', base, flags=re.IGNORECASE)
    return base.strip()

def normalize_string(s: str) -> str:
    """Normalize string for comparison."""
    # Lowercase
    s = s.lower()
    # Remove special chars except spaces
    s = re.sub(r'[^\w\s]', '', s)
    # Normalize whitespace
    s = re.sub(r'\s+', ' ', s)
    return s.strip()
```

### Conservative Matching Rules

**Do NOT merge as duplicates unless high confidence:**
- Remix vs original
- Instrumental vs original
- Karaoke vs original
- Extended version vs original
- Reprise vs original
- Different years (unless within 1 year and all other metadata matches)
- Different artists (unless featuring variations)

**Merge criteria (high confidence):**
- Same normalized title + artist + album + year
- Same normalized title + artist + album (year missing)
- Same normalized title + artist (album missing, duration matches within 5%)

## Download Planner Architecture

### Planning Pipeline

```python
class DownloadPlanner:
    """Plan downloads with cross-category/source deduplication."""
    
    def plan_downloads(self, discovered_songs: List[Song]) -> DownloadPlan:
        """
        Generate download plan from discovered songs.
        
        Steps:
        1. Canonicalize each discovered song
        2. Check library for existing songs
        3. Aggregate source variants
        4. Select best source per canonical song
        5. Filter already-owned songs
        6. Check for quality upgrades
        7. Generate final download queue
        """
        plan = DownloadPlan()
        
        for song in discovered_songs:
            # Step 1: Canonicalize
            canonical = self.canonicalize(song)
            
            # Step 2: Check library
            existing = self.library.get_by_canonical(canonical.hash)
            
            if existing:
                # Step 6: Check for quality upgrade
                if self.should_upgrade(existing, song):
                    plan.upgrades.append(UpgradePlan(existing, song))
                else:
                    plan.owned.append(existing)
            else:
                # Step 3: Aggregate source variants
                self.add_source_variant(canonical, song)
        
        # Step 4: Select best sources
        for canonical in plan.new_songs:
            best_source = self.select_best_source(canonical)
            plan.downloads.append(best_source)
        
        return plan
    
    def select_best_source(self, canonical: CanonicalSong) -> SourceSelection:
        """Select best source variant based on quality, reliability, etc."""
        sources = canonical.source_variants
        
        # Sort by priority
        ranked = sorted(sources, key=self.source_ranking_key, reverse=True)
        
        return SourceSelection(
            canonical=canonical,
            primary=ranked[0],
            fallbacks=ranked[1:]
        )
    
    def source_ranking_key(self, source: SongSource) -> tuple:
        """Priority: availability > quality > reliability > size"""
        return (
            source.is_available,
            source.quality_kbps or 0,
            source.reliability_score,
            -(source.file_size_bytes or 0)  # Prefer smaller if same quality
        )
```

### Download Plan Structure

```python
@dataclass
class DownloadPlan:
    """Result of download planning."""
    
    raw_discovered: int
    unique_canonical: int
    owned: List[LibrarySong]
    new_songs: List[SourceSelection]
    upgrades: List[UpgradePlan]
    
    @property
    def total_to_download(self) -> int:
        return len(self.new_songs) + len(self.upgrades)
```

### Concurrency Control

```python
class DownloadRegistry:
    """Central registry to prevent concurrent duplicate downloads."""
    
    def __init__(self, db: SQLiteDatabase):
        self.db = db
        self._lock = threading.RLock()
    
    def acquire_download_slot(self, song_id: int) -> bool:
        """
        Atomically acquire download slot for a song.
        
        Returns True if acquired, False if already downloading.
        Uses database-level locking for thread safety.
        """
        with self._lock:
            # Check current state
            song = self.db.get_song(song_id)
            if song.state in ['DOWNLOADING', 'QUEUED']:
                return False
            
            # Transition to DOWNLOADING
            self.db.update_song_state(song_id, 'DOWNLOADING')
            return True
    
    def release_download_slot(self, song_id: int, success: bool):
        """Release download slot and update state."""
        with self._lock:
            new_state = 'COMPLETED' if success else 'FAILED'
            self.db.update_song_state(song_id, new_state)
```

## Architecture Components

### New Modules

```
library/
├── __init__.py
├── database.py          # SQLiteDatabase class
├── models.py            # LibrarySong, SongSource, Download, etc.
├── canonical.py         # Canonical identity system
├── planner.py           # DownloadPlanner
├── registry.py          # DownloadRegistry for concurrency
├── importer.py          # Library import from existing files
└── migrator.py          # Database migrations
```

### Modified Components

**Scrapers** - No changes to base contract, but:
- Return richer metadata when available
- Include source reliability tracking

**Downloader** - Enhancements:
- Integrate with DownloadRegistry
- Update library state during download
- Handle quality upgrades (backup old file)
- Update source reliability scores

**GUI/TUI** - Major changes:
- Add library-centric views
- Add download planning UI
- Show ownership status
- Show source variants
- Add upgrade prompts
- Keep source-centric view as advanced option

**Settings** - Add:
- Library locations configuration
- Canonicalization preferences
- Upgrade policy settings
- Database location settings

## Implementation Phases

### Phase 1: Core Library Infrastructure (Highest Priority)

**Objective**: Establish SQLite database and canonical identity system

**Tasks**:
1. Create `library/` module structure
2. Implement `database.py` with SQLiteDatabase class
3. Implement database schema and migrations
4. Implement `canonical.py` with canonical identity system
5. Implement `models.py` with library data models
6. Add database initialization to app startup
7. Add schema version tracking

**Files to Create**:
- `library/__init__.py`
- `library/database.py`
- `library/models.py`
- `library/canonical.py`
- `library/migrator.py`

**Files to Modify**:
- `config/settings.py` - Add library configuration
- `main.py` - Initialize database on startup
- `gui.py` - Initialize database on startup
- `tui.py` - Initialize database on startup

**Tests**:
- Database connection and schema creation
- Canonical hash computation
- Model serialization/deserialization
- Migration system

**Acceptance Criteria**:
- Database created in user data directory
- Schema version tracking works
- Canonical hash is deterministic
- Models can be persisted and retrieved

### Phase 2: Song Discovery Integration

**Objective**: Integrate scrapers with library system during discovery

**Tasks**:
1. Implement `library/importer.py` stub (schema ready for future)
2. Modify scrapers to return canonical metadata
3. Implement discovery-to-library pipeline
4. Track discovery context in database
5. Implement source variant aggregation

**Files to Create**:
- `library/importer.py` (stub)

**Files to Modify**:
- `scrapers/base.py` - Add canonical metadata extraction
- `scrapers/isaimini.py` - Extract richer metadata
- `scrapers/masstamilan.py` - Extract richer metadata
- `scrapers/friendstamilmp3.py` - Extract richer metadata
- `gui.py` - Integrate library during discovery
- `tui.py` - Integrate library during discovery

**Tests**:
- Discovery creates library entries
- Source variants are aggregated
- Discovery context is tracked

**Acceptance Criteria**:
- Discovered songs are canonicalized
- Source variants are stored
- Discovery context is tracked
- No duplicate canonical entries

### Phase 3: Download Planning

**Objective**: Implement intelligent download planning

**Tasks**:
1. Implement `library/planner.py` with DownloadPlanner
2. Implement source ranking algorithm
3. Implement upgrade detection logic
4. Integrate planner into GUI/TUI
5. Show planning results to user

**Files to Create**:
- `library/planner.py`

**Files to Modify**:
- `gui.py` - Replace direct download with planned download
- `tui.py` - Replace direct download with planned download
- Add planning UI to show stats (discovered/owned/new)

**Tests**:
- Planning deduplicates correctly
- Source ranking works
- Upgrade detection works
- Cross-category deduplication verified

**Acceptance Criteria**:
- Planning shows correct stats (discovered/owned/new)
- Only new songs are queued
- Upgrades are identified
- User can review before download

### Phase 4: Download Execution & Concurrency

**Objective**: Integrate download registry and state management

**Tasks**:
1. Implement `library/registry.py` with DownloadRegistry
2. Modify downloader to use registry
3. Update library state during download
4. Handle quality upgrades (backup old file)
5. Update source reliability scores
6. Ensure atomic state transitions

**Files to Create**:
- `library/registry.py`

**Files to Modify**:
- `downloaders/http_downloader.py` - Integrate registry
- `gui.py` - Update state in UI
- `tui.py` - Update state in UI

**Tests**:
- Concurrent duplicate prevention
- State transitions are atomic
- Quality upgrades work correctly
- Source reliability updates

**Acceptance Criteria**:
- Same song never downloads twice concurrently
- State transitions are consistent
- Quality upgrades preserve old file until success
- Source reliability reflects actual success rate

### Phase 5: Library Import (Schema-Ready)

**Objective**: Implement filesystem import using existing canonicalization

**Tasks**:
1. Complete `library/importer.py` implementation
2. Scan library directories for MP3 files
3. Extract metadata using mutagen
4. Canonicalize and register in library
5. Handle conflicts with existing entries
6. Add import UI to GUI/TUI

**Files to Modify**:
- `library/importer.py` - Complete implementation
- `gui.py` - Add import UI
- `tui.py` - Add import UI

**Tests**:
- Import scans directories correctly
- Metadata extraction works
- Canonicalization matches discovery
- Conflicts are handled

**Acceptance Criteria**:
- Existing MP3 files are recognized
- Imported songs match discovered songs
- User can trigger import manually
- Import progress is shown

### Phase 6: UI Redesign (Library-Centric)

**Objective**: Redesign UI around library concept while keeping source view

**Tasks**:
1. Design new library-centric UI layout
2. Implement library browser view
3. Implement download queue view
4. Implement song details view (with source variants)
5. Keep source-centric view as advanced option
6. Ensure both views use same backend

**Files to Modify**:
- `gui.py` - Major UI redesign
- `tui.py` - Major UI redesign

**Tests**:
- Library view shows all songs
- Queue view shows active downloads
- Source variants are displayed
- Both views share backend

**Acceptance Criteria**:
- Library view is primary interface
- Source view remains available
- Both views use same library backend
- UI shows ownership status

### Phase 7: Playwright Async Fix

**Objective**: Fix Playwright sync API / asyncio interaction warning

**Tasks**:
1. Investigate the warning in MassTamilan scraper
2. Determine if async Playwright is needed
3. Implement proper async/sync separation
4. Test with both async and sync contexts

**Files to Modify**:
- `scrapers/masstamilan.py`
- `scrapers/isaimini.py` (if needed)

**Tests**:
- No asyncio warnings
- Works in both contexts

**Acceptance Criteria**:
- No warnings in logs
- Scrapers work in all contexts

### Phase 8: Migration & Testing

**Objective**: Migrate existing users and validate system

**Tasks**:
1. Design migration strategy for existing users
2. Implement migration script
3. Create comprehensive test suite
4. Test with realistic data
5. Verify cross-category duplicates
6. Verify cross-source duplicates
7. Verify concurrent duplicate prevention
8. Verify existing-library detection
9. Verify failed-source fallback

**Files to Create**:
- `scripts/migrate_existing.py`
- `tests/test_library_integration.py`
- `tests/test_canonicalization.py`
- `tests/test_download_planning.py`

**Tests**:
- Migration preserves existing functionality
- Cross-category deduplication works
- Cross-source deduplication works
- Concurrent downloads are safe
- Library import works
- Quality upgrades work

**Acceptance Criteria**:
- Existing users can migrate without data loss
- All automated tests pass
- Manual testing validates key scenarios
- Performance is acceptable

## Migration Strategy for Existing Users

### Migration Steps

1. **Backup existing data**
   - Copy existing music library
   - Export settings.json

2. **Initialize new database**
   - Create library.db in user data directory
   - Run schema migrations

3. **Import existing files**
   - Scan existing music directory
   - Extract metadata with mutagen
   - Canonicalize and register in library
   - Mark as OWNED state

4. **Migrate settings**
   - Preserve output directory as primary library location
   - Preserve source configurations
   - Preserve download preferences

5. **Verify migration**
   - Show migration summary to user
   - Highlight any conflicts or issues
   - Allow user to review before committing

### Rollback Plan

- Keep backup of old files
- Database can be deleted to revert
- Settings migration is non-destructive

## Testing Strategy

### Unit Tests

- Canonical hash computation
- Database operations
- Model serialization
- Source ranking
- Upgrade detection

### Integration Tests

- Discovery → Library pipeline
- Planning → Download pipeline
- Concurrency control
- State transitions

### End-to-End Tests

- Cross-category deduplication
- Cross-source deduplication
- Quality upgrades
- Library import
- Migration

### Performance Tests

- Large library (10,000+ songs)
- Concurrent download stress test
- Database query performance

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Canonical hash collisions | High | Use SHA256, include multiple metadata fields |
| Database corruption | High | Regular backups, integrity checks |
| Performance degradation | Medium | Index optimization, query profiling |
| Migration data loss | High | Backup before migration, verification |
| Concurrent race conditions | High | Database-level locking, transactional updates |
| Source reliability tracking accuracy | Low | Start with neutral scores, update gradually |
| UI complexity | Medium | Keep source view as fallback, iterative design |

## Files Changed Summary

### New Files
- `library/__init__.py`
- `library/database.py`
- `library/models.py`
- `library/canonical.py`
- `library/planner.py`
- `library/registry.py`
- `library/importer.py`
- `library/migrator.py`
- `scripts/migrate_existing.py`
- `tests/test_library_integration.py`
- `tests/test_canonicalization.py`
- `tests/test_download_planning.py`

### Modified Files
- `config/settings.py` - Add library configuration
- `scrapers/base.py` - Add canonical metadata extraction
- `scrapers/isaimini.py` - Extract richer metadata
- `scrapers/masstamilan.py` - Extract richer metadata, fix Playwright
- `scrapers/friendstamilmp3.py` - Extract richer metadata
- `downloaders/http_downloader.py` - Integrate registry
- `gui.py` - Major redesign, integrate library
- `tui.py` - Major redesign, integrate library
- `main.py` - Initialize database

### Files Unchanged
- `models/song.py` - Keep for compatibility (may deprecate later)
- Existing test structure
- Documentation (will update after implementation)

## Next Steps

After approval of this plan:

1. Begin Phase 1 implementation
2. Create database schema
3. Implement canonical identity system
4. Test with sample data
5. Proceed incrementally through phases
6. Validate each phase before proceeding
7. Document changes as implementation progresses
