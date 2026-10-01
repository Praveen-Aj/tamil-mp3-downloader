import React, { useState, useEffect, useRef } from 'react';
import { Search, RefreshCw, HardDrive, Music, Film, Users, Play, X, Menu } from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { searchApi } from '../../api/endpoints';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { Song, Movie, Artist } from '../../api/types';
import { api } from '../../api/client';

interface HeaderProps {
  onMenuClick: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onMenuClick }) => {
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

  // Clear global header search bar when navigating to non-search views
  useEffect(() => {
    if (currentView !== 'search') {
      setSearchQuery('');
      setResults(null);
      setIsDropdownOpen(false);
    }
  }, [currentView]);

  const formatStorage = (bytes?: number) => {
    if (!bytes) return '0 MB';
    const mb = bytes / (1024 * 1024);
    if (mb > 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${Math.round(mb)} MB`;
  };

  const getPageTitle = () => {
    switch (currentView) {
      case 'dashboard':
        return 'Home';
      case 'songs':
        return 'Songs';
      case 'movies':
        return 'Movies & Soundtracks';
      case 'artists':
        return 'Artists';
      case 'charts':
        return 'Charts';
      case 'playlists':
        return 'Playlists';
      case 'favorites':
        return 'Favorites';
      case 'search':
        return 'Search';
      case 'downloads':
        return 'Downloads';
      case 'imports':
        return 'Import';
      case 'settings':
        return 'Settings';
      case 'movie_detail':
        return 'Soundtrack Detail';
      case 'artist_detail':
        return 'Artist Discography';
      default:
        return 'Music';
    }
  };

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      setGlobalSearchQuery(searchQuery.trim());
      navigateTo('search');
      setIsDropdownOpen(false);
    }
  };

  return (
    <header
      className="header-container"
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
        gap: '12px',
      }}
    >
      {/* Hamburger (mobile only) */}
      <button
        className="btn-icon header-hamburger"
        onClick={onMenuClick}
        aria-label="Open menu"
        style={{ width: '36px', height: '36px', flexShrink: 0 }}
      >
        <Menu size={20} />
      </button>

      {/* Page Title */}
      <h1 className="title-display" style={{ fontSize: '18px', fontWeight: 700, color: 'var(--text-primary)', flexShrink: 0 }}>
        {getPageTitle()}
      </h1>

      {/* Global Search Bar — hidden on mobile, shown on desktop */}
      <div ref={dropdownRef} style={{ position: 'relative', flex: 1, maxWidth: '380px' }} className="header-search-full">
        <form
          onSubmit={handleSearchSubmit}
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
          <button
            type="submit"
            aria-label="Execute search"
            style={{
              background: 'none',
              border: 'none',
              padding: 0,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              color: 'var(--text-muted)',
            }}
          >
            <Search size={16} />
          </button>
          <input
            type="text"
            placeholder="Search songs, movies, artists..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => {
              if (results) setIsDropdownOpen(true);
            }}
            style={{
              flex: 1,
              fontSize: '13px',
              color: 'var(--text-primary)',
              background: 'transparent',
              border: 'none',
              outline: 'none',
            }}
            aria-label="Global search input"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => {
                setSearchQuery('');
                setResults(null);
                setIsDropdownOpen(false);
              }}
              aria-label="Clear search input"
              style={{
                background: 'none',
                border: 'none',
                padding: 0,
                cursor: 'pointer',
                color: 'var(--text-muted)',
              }}
            >
              <X size={14} />
            </button>
          )}
        </form>

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
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
                          <img
                            src={api.getArtworkUrl('song', s.id, 56, 56)}
                            alt={s.title}
                            style={{
                              width: '28px',
                              height: '28px',
                              borderRadius: '4px',
                              objectFit: 'cover',
                              flexShrink: 0,
                              backgroundColor: 'var(--bg-surface-active)',
                            }}
                            onError={(e) => {
                              (e.target as HTMLElement).style.display = 'none';
                            }}
                          />
                          <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            <span style={{ fontWeight: 500, fontSize: '13px' }}>{s.title}</span>
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '6px' }}>
                              {s.artist || s.album}
                            </span>
                          </div>
                        </div>
                        <Play size={12} color="var(--text-muted)" style={{ flexShrink: 0, marginLeft: '8px' }} />
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
                          gap: '10px',
                          padding: '6px 8px',
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <img
                          src={api.getArtworkUrl('movie', m.id, 60, 60)}
                          alt={m.title || m.name}
                          style={{
                            width: '24px',
                            height: '32px',
                            borderRadius: '3px',
                            objectFit: 'cover',
                            flexShrink: 0,
                            backgroundColor: 'var(--bg-surface-active)',
                          }}
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
                        <div style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          <span style={{ fontWeight: 500, fontSize: '13px' }}>{m.title || m.name}</span>
                          {m.year && (
                            <span style={{ fontSize: '11px', color: 'var(--text-muted)', marginLeft: '6px' }}>({m.year})</span>
                          )}
                        </div>
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
                          gap: '10px',
                          padding: '6px 8px',
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer',
                        }}
                        onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                        onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'transparent')}
                      >
                        <img
                          src={api.getArtworkUrl('artist', a.id, 56, 56)}
                          alt={a.name}
                          style={{
                            width: '28px',
                            height: '28px',
                            borderRadius: '50%',
                            objectFit: 'cover',
                            flexShrink: 0,
                            backgroundColor: 'var(--bg-surface-active)',
                          }}
                          onError={(e) => {
                            (e.target as HTMLElement).style.display = 'none';
                          }}
                        />
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

      {/* Right side: storage info + refresh — hidden on mobile */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        {/* Storage Badge */}
        <div
          className="header-stats-badge"
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            fontSize: '12px',
            color: 'var(--text-secondary)',
            backgroundColor: 'var(--bg-surface)',
            padding: '5px 10px',
            borderRadius: 'var(--radius-pill)',
            border: '1px solid var(--border-subtle)',
          }}
        >
          <HardDrive size={13} color="var(--text-muted)" />
          <span>{formatStorage(stats?.total_storage_bytes)}</span>
        </div>

        {/* Refresh Button */}
        <button
          onClick={() => refreshStats()}
          title="Refresh library"
          className="btn-icon"
          style={{ width: '32px', height: '32px' }}
          aria-label="Refresh library"
        >
          <RefreshCw size={15} />
        </button>
      </div>
    </header>
  );
};
