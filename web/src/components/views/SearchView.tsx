import React, { useEffect, useState, useCallback } from 'react';
import {
  Search as SearchIcon,
  Music,
  Film,
  Users,
  Play,
  Download,
  FolderOpen,
} from 'lucide-react';
import { searchApi, downloadsApi, songsApi, moviesApi, artistsApi } from '../../api/endpoints';
import { Song, Movie, Artist } from '../../api/types';
import { useApp } from '../../context/AppContext';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { Button } from '../common/Button';
import { Card } from '../common/Card';
import { QualityBadge, DownloadStateBadge } from '../common/Badge';
import { api } from '../../api/client';

export const SearchView: React.FC = () => {
  const { globalSearchQuery, setGlobalSearchQuery, navigateTo, showToast, refreshStats } = useApp();
  const { playSong } = useAudioPlayer();

  const [activeTab, setActiveTab] = useState<'all' | 'songs' | 'movies' | 'artists'>('all');
  const [songs, setSongs] = useState<Song[]>([]);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [artists, setArtists] = useState<Artist[]>([]);
  const [loading, setLoading] = useState(false);

  const executeSearch = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const res = await searchApi.searchGlobal(q.trim(), 50);
      if (res.success && res.data) {
        setSongs(res.data.songs || []);
        setMovies(res.data.movies || []);
        setArtists(res.data.artists || []);
      }
    } catch (err: any) {
      showToast(err.message || 'Search failed', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    if (globalSearchQuery) {
      executeSearch(globalSearchQuery);
    }
  }, [globalSearchQuery, executeSearch]);

  const handleDownloadSong = async (songId: number, title: string) => {
    try {
      const res = await downloadsApi.queueSongs([songId]);
      if (res.success) {
        showToast(`Queued "${title}" for download`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue download', 'error');
    }
  };

  const handleDownloadMovie = async (movieId: number, title: string) => {
    try {
      const res = await moviesApi.startDownload(movieId);
      if (res.success) {
        showToast(`Queued ${res.data.queued_count} songs from "${title}"`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to download movie songs', 'error');
    }
  };

  const handleDownloadArtist = async (artistId: number, name: string) => {
    try {
      const res = await artistsApi.startDownload(artistId);
      if (res.success) {
        showToast(`Queued ${res.data.queued_count} songs by "${name}"`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to download artist songs', 'error');
    }
  };

  const totalResults = songs.length + movies.length + artists.length;

  return (
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Search Input Bar */}
      <div className="glass-panel" style={{ padding: '20px 24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', gap: '12px' }}>
          <div
            style={{
              flex: 1,
              display: 'flex',
              alignItems: 'center',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-md)',
              padding: '10px 16px',
              gap: '12px',
            }}
          >
            <SearchIcon size={18} color="var(--accent-primary)" />
            <input
              type="text"
              placeholder="Search by title, artist, composer, movie soundtrack..."
              value={globalSearchQuery}
              onChange={(e) => setGlobalSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && executeSearch(globalSearchQuery)}
              style={{ flex: 1, fontSize: '14px', color: 'var(--text-primary)' }}
              aria-label="Search all library tracks"
            />
          </div>
          <Button variant="primary" onClick={() => executeSearch(globalSearchQuery)}>
            Search
          </Button>
        </div>

        {/* Tab Filters */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            {[
              { id: 'all', label: `All (${totalResults})` },
              { id: 'songs', label: `Songs (${songs.length})` },
              { id: 'movies', label: `Movies (${movies.length})` },
              { id: 'artists', label: `Artists (${artists.length})` },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`btn ${activeTab === tab.id ? 'btn-primary' : 'btn-secondary'}`}
                style={{ padding: '6px 14px', fontSize: '12px' }}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            {loading ? 'Searching catalog...' : `${totalResults} matching results`}
          </div>
        </div>
      </div>

      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          Searching across songs, movie soundtracks, and artist rosters...
        </div>
      ) : totalResults === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          No catalog matches found for "{globalSearchQuery}".
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
          {/* Songs Section */}
          {(activeTab === 'all' || activeTab === 'songs') && songs.length > 0 && (
            <div className="glass-panel" style={{ padding: '24px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <Music size={18} color="var(--accent-primary)" />
                <h3 className="title-display" style={{ fontSize: '16px', margin: 0 }}>
                  Matching Songs ({songs.length})
                </h3>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                {songs.map((song) => (
                  <div
                    key={song.id}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 12px',
                      borderRadius: 'var(--radius-md)',
                      backgroundColor: 'rgba(255, 255, 255, 0.02)',
                      border: '1px solid var(--border-subtle)',
                      transition: 'background var(--transition-fast)',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.02)')}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0, flex: 1 }}>
                      <button
                        onClick={() => playSong(song, songs)}
                        className="btn-icon"
                        style={{ width: '32px', height: '32px' }}
                        title="Play stream"
                      >
                        <Play size={13} fill="currentColor" />
                      </button>
                      <img
                        src={api.getArtworkUrl('song', song.id, 40, 40)}
                        alt={song.title}
                        style={{ width: '32px', height: '32px', borderRadius: '4px', objectFit: 'cover' }}
                        onError={(e) => {
                          (e.target as HTMLImageElement).src =
                            'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="%231e293b"><rect width="32" height="32"/></svg>';
                        }}
                      />
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontWeight: 600, fontSize: '13px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {song.title}
                        </div>
                        <div style={{ fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {song.artist || song.album || 'Unknown'} {song.year ? `• ${song.year}` : ''}
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <QualityBadge quality={song.quality} />
                      <DownloadStateBadge state={song.download_state || song.state} />
                      {song.download_state !== 'DOWNLOADED' ? (
                        <button
                          onClick={() => handleDownloadSong(song.id, song.title)}
                          className="btn-icon"
                          style={{ width: '28px', height: '28px', color: 'var(--accent-primary)' }}
                          title="Download song"
                        >
                          <Download size={14} />
                        </button>
                      ) : (
                        <button
                          onClick={() => songsApi.openFolder(song.id)}
                          className="btn-icon"
                          style={{ width: '28px', height: '28px', color: 'var(--color-success)' }}
                          title="Reveal file in Explorer"
                        >
                          <FolderOpen size={14} />
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Movies Section */}
          {(activeTab === 'all' || activeTab === 'movies') && movies.length > 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <Film size={18} color="var(--accent-secondary)" />
                <h3 className="title-display" style={{ fontSize: '16px', margin: 0 }}>
                  Soundtrack Albums ({movies.length})
                </h3>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '16px' }}>
                {movies.map((movie) => (
                  <Card
                    key={movie.id}
                    onClick={() => navigateTo('movie_detail', movie.id)}
                    className="glass-card"
                    style={{ display: 'flex', flexDirection: 'column', padding: '12px' }}
                  >
                    <img
                      src={api.getArtworkUrl('movie', movie.id, 200, 200)}
                      alt={movie.title || movie.name}
                      style={{ width: '100%', aspectRatio: '1', borderRadius: '8px', objectFit: 'cover', marginBottom: '10px' }}
                      onError={(e) => {
                        (e.target as HTMLImageElement).src =
                          'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" fill="%231e1b4b"><rect width="200" height="200"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23fff" font-size="24">🎬</text></svg>';
                      }}
                    />
                    <div style={{ fontWeight: 700, fontSize: '13px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {movie.title || movie.name}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {movie.year || 'Soundtrack'} • {movie.total_songs ?? 0} tracks
                    </div>
                    <div style={{ marginTop: '10px', display: 'flex', justifyContent: 'flex-end' }}>
                      <Button
                        size="sm"
                        variant="primary"
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadMovie(movie.id, movie.title || movie.name || '');
                        }}
                      >
                        <Download size={12} /> Download
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* Artists Section */}
          {(activeTab === 'all' || activeTab === 'artists') && artists.length > 0 && (
            <div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                <Users size={18} color="#f59e0b" />
                <h3 className="title-display" style={{ fontSize: '16px', margin: 0 }}>
                  Artists & Composers ({artists.length})
                </h3>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: '16px' }}>
                {artists.map((artist) => (
                  <Card
                    key={artist.id}
                    onClick={() => navigateTo('artist_detail', artist.id)}
                    className="glass-card"
                    style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', padding: '16px' }}
                  >
                    <img
                      src={api.getArtworkUrl('artist', artist.id, 100, 100)}
                      alt={artist.name}
                      style={{ width: '72px', height: '72px', borderRadius: '50%', objectFit: 'cover', marginBottom: '10px' }}
                      onError={(e) => {
                        (e.target as HTMLImageElement).src =
                          'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100" fill="%230f172a"><rect width="100" height="100"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23fff" font-size="20">👤</text></svg>';
                      }}
                    />
                    <div style={{ fontWeight: 700, fontSize: '13px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', width: '100%' }}>
                      {artist.name}
                    </div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {(artist.total_songs ?? artist.total_tracks) ?? 0} tracks
                    </div>
                    <div style={{ marginTop: '10px', width: '100%' }}>
                      <Button
                        size="sm"
                        variant="primary"
                        style={{ width: '100%' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          handleDownloadArtist(artist.id, artist.name);
                        }}
                      >
                        <Download size={12} /> Download
                      </Button>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
