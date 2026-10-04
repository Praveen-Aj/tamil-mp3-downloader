import React, { useEffect, useState, useCallback } from 'react';
import {
  Heart,
  Play,
  Download,
  FolderOpen,
  ChevronLeft,
  ChevronRight,
  Music,
} from 'lucide-react';
import { songsApi, downloadsApi } from '../../api/endpoints';
import { Song } from '../../api/types';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { useApp } from '../../context/AppContext';
import { Button } from '../common/Button';
import { QualityBadge, DownloadStateBadge } from '../common/Badge';
import { api } from '../../api/client';

export const FavoritesView: React.FC = () => {
  const { playSong } = useAudioPlayer();
  const { showToast, refreshStats, navigateTo } = useApp();

  const [songs, setSongs] = useState<Song[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [loading, setLoading] = useState(false);

  const loadFavorites = useCallback(async () => {
    setLoading(true);
    try {
      const res = await songsApi.getFavorites({ page, page_size: pageSize });
      if (res.success && res.data) {
        setSongs(res.data.items || []);
        setTotal(res.data.total || 0);
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to load favorite songs', 'error');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, showToast]);

  useEffect(() => {
    loadFavorites();
  }, [loadFavorites]);

  const handleDownload = async (songId: number, title: string) => {
    try {
      const res = await downloadsApi.queueSongs([songId]);
      if (res.success) {
        showToast(`Queued "${title}" for download`, 'success');
        refreshStats();
        loadFavorites();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue download', 'error');
    }
  };

  const handleRemoveFavorite = async (songId: number, title: string) => {
    try {
      await songsApi.toggleFavorite(songId, false);
      showToast(`Removed "${title}" from favorites`, 'info');
      loadFavorites();
    } catch (err: any) {
      showToast(err.message || 'Failed to update favorite', 'error');
    }
  };

  const handleOpenFolder = async (songId: number) => {
    try {
      await songsApi.openFolder(songId);
    } catch (err: any) {
      showToast(err.message || 'Failed to open file folder', 'error');
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="view-container" style={{ gap: '20px' }}>
      {/* Header */}
      <div className="view-header">
        <div className="view-header-title">
          <div
            className="view-header-icon"
            style={{
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              borderColor: 'rgba(239, 68, 68, 0.3)',
              color: 'var(--color-error)',
            }}
          >
            <Heart size={20} fill="currentColor" />
          </div>
          <div>
            <h1 className="view-title">Favorite Tracks</h1>
            <div className="view-subtitle">
              {total} {total === 1 ? 'starred song' : 'starred songs'} in your personal collection
            </div>
          </div>
        </div>

        {songs.length > 0 && (
          <Button
            variant="primary"
            onClick={() => playSong(songs[0], songs)}
            aria-label="Play all favorites"
          >
            <Play size={16} fill="currentColor" /> Play All
          </Button>
        )}
      </div>

      {/* Favorites - Desktop table */}
      <div className="table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Track</th>
              <th>Soundtrack / Album</th>
              <th style={{ width: '85px' }}>Quality</th>
              <th style={{ width: '115px' }}>Status</th>
              <th style={{ textAlign: 'right', width: '90px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  Loading favorites...
                </td>
              </tr>
            ) : songs.length === 0 ? (
              <tr>
                <td colSpan={5} style={{ textAlign: 'center', padding: '56px 20px', color: 'var(--text-muted)' }}>
                  <div style={{ width: '56px', height: '56px', borderRadius: '50%', backgroundColor: 'rgba(239, 68, 68, 0.1)', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', marginBottom: '14px' }}>
                    <Heart size={26} color="var(--color-error)" />
                  </div>
                  <h3 style={{ margin: '0 0 6px 0', fontSize: '16px', fontWeight: 700, color: 'var(--text-primary)' }}>
                    No favorite tracks yet
                  </h3>
                  <p style={{ margin: '0 auto 16px auto', color: 'var(--text-secondary)', fontSize: '13px', maxWidth: '360px', lineHeight: 1.5 }}>
                    Click the heart icon on any track while browsing or listening to build your personal Tamil music collection.
                  </p>
                  <Button variant="secondary" size="sm" onClick={() => navigateTo('songs')}>
                    Browse Song Library
                  </Button>
                </td>
              </tr>
            ) : (
              songs.map((song) => (
                <tr key={song.id}>
                  {/* Track: Art with play overlay + Title + Artist */}
                  <td style={{ minWidth: '220px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div
                        onClick={() => playSong(song, songs)}
                        style={{
                          width: '40px',
                          height: '40px',
                          borderRadius: 'var(--radius-sm)',
                          overflow: 'hidden',
                          position: 'relative',
                          backgroundColor: '#101014',
                          cursor: 'pointer',
                          flexShrink: 0,
                        }}
                        className="track-art-wrap"
                        title={`Play ${song.title}`}
                      >
                        <img
                          src={api.getArtworkUrl('song', song.id, 80, 80)}
                          alt={song.title}
                          style={{
                            width: '100%',
                            height: '100%',
                            objectFit: 'cover',
                          }}
                          loading="lazy"
                          onError={(e) => {
                            (e.target as HTMLImageElement).src =
                              'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" fill="%23101014"><rect width="40" height="40"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="14">🎵</text></svg>';
                          }}
                        />
                        <div
                          style={{
                            position: 'absolute',
                            inset: 0,
                            backgroundColor: 'rgba(0, 0, 0, 0.45)',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            color: '#ffffff',
                            opacity: 0,
                            transition: 'opacity 150ms ease',
                          }}
                          className="play-overlay"
                        >
                          <Play size={14} fill="currentColor" />
                        </div>
                      </div>

                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div
                          onClick={() => playSong(song, songs)}
                          style={{
                            fontWeight: 600,
                            color: '#f8fafc',
                            fontSize: '13.5px',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                            cursor: 'pointer',
                          }}
                          title={song.title}
                        >
                          {song.title}
                        </div>
                        <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: '2px' }}>
                          {song.artist || 'Unknown Artist'}
                        </div>
                      </div>
                    </div>
                  </td>

                  <td style={{ color: 'var(--text-secondary)', fontSize: '12.5px' }}>
                    {song.album || '-'} {song.year ? <span style={{ color: 'var(--text-muted)', fontSize: '11.5px' }}>({song.year})</span> : ''}
                  </td>
                  <td>
                    <QualityBadge quality={song.quality} />
                  </td>
                  <td>
                    <DownloadStateBadge state={song.download_state || song.state} />
                  </td>

                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '3px' }}>
                      {song.download_state !== 'DOWNLOADED' ? (
                        <button
                          onClick={() => handleDownload(song.id, song.title)}
                          className="btn-icon"
                          style={{ width: '28px', height: '28px', color: 'var(--accent-primary)' }}
                          title="Download song"
                          aria-label={`Download ${song.title}`}
                        >
                          <Download size={14} />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleOpenFolder(song.id)}
                          className="btn-icon"
                          style={{ width: '28px', height: '28px', color: 'var(--color-success)' }}
                          title="Reveal in Explorer"
                          aria-label="Reveal in Explorer"
                        >
                          <FolderOpen size={14} />
                        </button>
                      )}

                      <button
                        onClick={() => handleRemoveFavorite(song.id, song.title)}
                        className="btn-icon"
                        style={{ width: '28px', height: '28px', color: 'var(--color-error)' }}
                        title="Remove from favorites"
                        aria-label={`Remove ${song.title} from favorites`}
                      >
                        <Heart size={14} fill="currentColor" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination */}
        {totalPages > 1 && (
          <div
            style={{
              padding: '14px 20px',
              borderTop: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              fontSize: '13px',
              color: 'var(--text-muted)',
            }}
          >
            <div>
              Showing {songs.length} of {total} favorites
            </div>

            <div style={{ display: 'flex', gap: '8px' }}>
              <Button
                variant="secondary"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                <ChevronLeft size={16} /> Previous
              </Button>
              <Button
                variant="secondary"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next <ChevronRight size={16} />
              </Button>
            </div>
          </div>
        )}
      </div>

      {/* Favorites - Mobile card list (hidden on desktop, shown on mobile via CSS) */}
      <div className="glass-panel mobile-cards-container" style={{ overflow: 'hidden' }}>
        {loading ? (
          <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>Loading...</div>
        ) : songs.length === 0 ? null : (
          songs.map((song) => (
            <div key={`m-${song.id}`} className="mobile-track-card">
              <img
                src={`/api/artwork/song/${song.id}?w=44&h=44`}
                alt={song.title}
                className="mobile-track-card__art"
                onError={(e) => {
                  (e.target as HTMLImageElement).src =
                    'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" fill="%23101014"><rect width="44" height="44"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="14">♪</text></svg>';
                }}
              />
              <div className="mobile-track-card__info">
                <div className="mobile-track-card__title">{song.title}</div>
                <div className="mobile-track-card__meta">
                  {[song.artist, song.album].filter(Boolean).join(' · ')}
                </div>
              </div>
              <div className="mobile-track-card__actions">
                <button
                  onClick={() => playSong(song, songs)}
                  className="btn-icon"
                  aria-label={`Play ${song.title}`}
                  style={{ width: '36px', height: '36px' }}
                >
                  <Play size={14} fill="currentColor" />
                </button>
                {song.download_state !== 'DOWNLOADED' ? (
                  <button
                    onClick={() => handleDownload(song.id, song.title)}
                    className="btn-icon"
                    aria-label={`Download ${song.title}`}
                    style={{ width: '36px', height: '36px', color: 'var(--accent-primary)' }}
                  >
                    <Download size={14} />
                  </button>
                ) : null}
                <button
                  onClick={() => handleRemoveFavorite(song.id, song.title)}
                  className="btn-icon"
                  aria-label={`Remove ${song.title} from favorites`}
                  style={{ width: '36px', height: '36px', color: 'var(--color-error)' }}
                >
                  <Heart size={14} fill="currentColor" />
                </button>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};
