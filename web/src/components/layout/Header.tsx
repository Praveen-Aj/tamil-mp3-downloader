import React, { useState, useEffect, useRef } from 'react';
import { Search, RefreshCw, HardDrive, Music, Film, Users, Play, X } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { searchApi } from '../../api/endpoints';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { Song, Movie, Artist } from '../../api/types';

export const Header: React.FC = () => {
  const { currentView, stats, refreshStats, navigateTo, setGlobalSearchQuery } = useApp();
  const { playSong } = useAudioPlayer();
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<{
    songs: Song[];
    movies: Movie[];
    artists: Artist[];
  } | null>(null);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Debounced search
  useEffect(() => {
    if (!searchQuery.trim()) {
      setResults(null);
      setIsDropdownOpen(false);
      return;
    }

    const timer = setTimeout(async () => {
      setIsSearching(true);
      try {
        const res = await searchApi.searchGlobal(searchQuery.trim(), 5);
        if (res.success && res.data) {
          setResults(res.data);
          setIsDropdownOpen(true);
        }
      } catch (err) {
        console.error('Search error:', err);
      } finally {
        setIsSearching(false);
      }
    }, 250);

    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Click outside listener
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const formatStorage = (bytes?: number) => {
    if (!bytes) return '0 MB';
    const mb = bytes / (1024 * 1024);
    if (mb > 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${Math.round(mb)} MB`;
  };

  const getPageTitle = () => {
    switch (currentView) {
      case 'dashboard':
        return 'Overview & Dashboard';
      case 'songs':
        return 'Song Library';
      case 'movies':
        return 'Soundtracks & Movies';
      case 'artists':
        return 'Artists & Composers';
      case 'charts':
        return 'Featured Top Charts';
      case 'playlists':
        return 'Playlists Studio';
      case 'favorites':
        return 'Favorite Tracks';
      case 'search':
        return 'Global Search Results';
      case 'downloads':
        return 'Download Engine & Queue';
      case 'imports':
        return 'Playlist URL Import';
      case 'settings':
        return 'System & Engine Settings';
      default:
        return 'Music Studio';
    }
  };

  return (
    <header
      style={{
        height: 'var(--header-height)',
        backgroundColor: 'var(--bg-header)',
        backdropFilter: 'blur(16px)',
        borderBottom: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 28px',
        position: 'relative',
        zIndex: 50,
      }}
    >
      {/* Title */}
      <h1 className="title-display" style={{ fontSize: '20px', fontWeight: 700, color: 'var(--text-primary)' }}>
        {getPageTitle()}
      </h1>

      {/* Global Search Bar */}
      <div ref={dropdownRef} style={{ position: 'relative', width: '380px' }}>
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-pill)',
            padding: '8px 14px',
            gap: '10px',
            transition: 'border-color var(--transition-fast)',
          }}
        >
          <Search size={16} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search songs, movies, artists..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && searchQuery.trim()) {
                setGlobalSearchQuery(searchQuery.trim());
                navigateTo('search');
                setIsDropdownOpen(false);
              }
            }}
            onFocus={() => {
              if (results) setIsDropdownOpen(true);
            }}
            style={{
              flex: 1,
              fontSize: '13px',
              color: 'var(--text-primary)',
            }}
            aria-label="Global search input"
          />
          {searchQuery && (
            <button
              onClick={() => {
                setSearchQuery('');
                setResults(null);
                setIsDropdownOpen(false);
              }}
              style={{ color: 'var(--text-muted)' }}
            >
              <X size={14} />
            </button>
          )}
        </div>

        {/* Search Results Dropdown */}
        {isDropdownOpen && results && (
          <div
            className="glass-panel"
            style={{
              position: 'absolute',
              top: 'calc(100% + 8px)',
              left: 0,
              right: 0,
              backgroundColor: 'var(--bg-modal)',
              boxShadow: 'var(--shadow-lg)',
              padding: '12px',
              maxHeight: '400px',
              overflowY: 'auto',
              borderRadius: 'var(--radius-md)',
            }}
          >
            {results.songs.length === 0 &&
            results.movies.length === 0 &&
            results.artists.length === 0 ? (
              <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-muted)' }}>
                No results found for "{searchQuery}"
              </div>
            ) : (
              <>
                {/* Songs */}
                {results.songs.length > 0 && (
                  <div style={{ marginBottom: '12px' }}>
                    <div
                      style={{
                        fontSize: '11px',
                        color: 'var(--text-muted)',
                        textTransform: 'uppercase',
                        fontWeight: 600,
                        padding: '4px 8px',
                      }}
                    >
                      Songs
                    </div>
                    {results.songs.map((s) => (
                      <div
                        key={s.id}
                        onClick={() => {
                          playSong(s);
                          setIsDropdownOpen(false);
                        }}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'space-between',
                          padding: '6px 8px',
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                          transition: 'background var(--transition-fast)',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0 }}>
                          <Music size={14} color="var(--accent-primary)" />
                          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            <span style={{ fontWeight: 500, fontSize: '13px' }}>{s.title}</span>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '6px' }}>
                              {s.artist || s.album}
                            </span>
                          </div>
                        </div>
                        <Play size={12} color="var(--text-muted)" />
                      </div>
                    ))}
                  </div>
                )}

                {/* Movies */}
                {results.movies.length > 0 && (
                  <div style={{ marginBottom: '12px' }}>
                    <div
                      style={{
                        fontSize: '11px',
                        color: 'var(--text-muted)',
                        textTransform: 'uppercase',
                        fontWeight: 600,
                        padding: '4px 8px',
                      }}
                    >
                      Movies
                    </div>
                    {results.movies.map((m) => (
                      <div
                        key={m.id}
                        onClick={() => {
                          navigateTo('movie_detail', m.id);
                          setIsDropdownOpen(false);
                        }}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          padding: '6px 8px',
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <Film size={14} color="var(--accent-secondary)" />
                        <span style={{ fontWeight: 500, fontSize: '13px' }}>{m.title || m.name}</span>
                        {m.year && (
                          <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>({m.year})</span>
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {/* Artists */}
                {results.artists.length > 0 && (
                  <div>
                    <div
                      style={{
                        fontSize: '11px',
                        color: 'var(--text-muted)',
                        textTransform: 'uppercase',
                        fontWeight: 600,
                        padding: '4px 8px',
                      }}
                    >
                      Artists
                    </div>
                    {results.artists.map((a) => (
                      <div
                        key={a.id}
                        onClick={() => {
                          navigateTo('artist_detail', a.id);
                          setIsDropdownOpen(false);
                        }}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          padding: '6px 8px',
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <Users size={14} color="#f59e0b" />
                        <span style={{ fontWeight: 500, fontSize: '13px' }}>{a.name}</span>
                      </div>
                    ))}
                  </div>
                )}

                {/* View all results button */}
                <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid var(--border-subtle)' }}>
                  <button
                    onClick={() => {
                      setGlobalSearchQuery(searchQuery.trim());
                      navigateTo('search');
                      setIsDropdownOpen(false);
                    }}
                    className="btn btn-secondary"
                    style={{ width: '100%', fontSize: '12px', padding: '6px 12px' }}
                  >
                    View all results for "{searchQuery}"
                  </button>
                </div>
              </>
            )}
          </div>
        )}
      </div>

      {/* Action Controls & Diagnostics */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
        {/* Storage Badge */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            backgroundColor: 'var(--bg-surface)',
            padding: '6px 12px',
            borderRadius: 'var(--radius-pill)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <HardDrive size={14} color="var(--accent-secondary)" />
          <span>{formatStorage(stats?.total_storage_bytes)}</span>
        </div>

        {/* Refresh Button */}
        <button
          onClick={() => refreshStats()}
          title="Refresh library metrics"
          className="btn-icon"
          style={{ width: '32px', height: '32px' }}
        >
          <RefreshCw size={15} />
        </button>
      </div>
    </header>
  );
};
