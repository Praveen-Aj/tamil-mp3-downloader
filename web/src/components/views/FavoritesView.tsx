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
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Header */}
      <div
        className="glass-panel"
        style={{
          padding: '24px 28px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '44px',
              height: '44px',
              borderRadius: '12px',
              backgroundColor: 'rgba(239, 68, 68, 0.15)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--color-error)',
            }}
          >
            <Heart size={22} fill="currentColor" />
          </div>
          <div>
            <h2 className="title-display" style={{ fontSize: '20px', margin: 0 }}>
              Favorite Tracks
            </h2>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
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

      {/* Favorites Table */}
      <div className="glass-panel" style={{ overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '50px' }}>Play</th>
              <th style={{ width: '50px' }}>Art</th>
              <th>Title</th>
              <th>Artist</th>
              <th>Album / Movie</th>
              <th>Year</th>
              <th>Quality</th>
              <th>Download State</th>
              <th style={{ textAlign: 'right', width: '130px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  Loading favorites...
                </td>
              </tr>
            ) : songs.length === 0 ? (
              <tr>
                <td colSpan={9} style={{ textAlign: 'center', padding: '50px 20px', color: 'var(--text-muted)' }}>
                  <Heart size={32} style={{ margin: '0 auto 12px', display: 'block', opacity: 0.4 }} />
                  <div>No favorite songs yet. Click the heart icon while playing or browsing songs to add favorites!</div>
                  <Button variant="secondary" size="sm" onClick={() => navigateTo('songs')} style={{ marginTop: '16px' }}>
                    Browse Song Library
                  </Button>
                </td>
              </tr>
            ) : (
              songs.map((song) => (
                <tr key={song.id}>
                  <td>
                    <button
                      onClick={() => playSong(song, songs)}
                      className="btn-icon"
                      style={{ width: '32px', height: '32px' }}
                      title="Play stream"
                      aria-label={`Play ${song.title}`}
                    >
                      <Play size={13} fill="currentColor" />
                    </button>
                  </td>

                  <td>
                    <img
                      src={api.getArtworkUrl('song', song.id, 40, 40)}
                      alt={song.title}
                      style={{
                        width: '36px',
                        height: '36px',
                        borderRadius: 'var(--radius-sm)',
                        objectFit: 'cover',
                        backgroundColor: 'var(--bg-surface-active)',
                        border: '1px solid var(--border-subtle)',
                      }}
                      onError={(e) => {
                        (e.target as HTMLImageElement).src =
                          'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" fill="%231e293b"><rect width="36" height="36"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%2364748b" font-size="12">🎵</text></svg>';
                      }}
                    />
                  </td>

                  <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{song.title}</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{song.artist || '—'}</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{song.album || '—'}</td>
                  <td style={{ color: 'var(--text-muted)' }}>{song.year || '—'}</td>
                  <td>
                    <QualityBadge quality={song.quality} />
                  </td>
                  <td>
                    <DownloadStateBadge state={song.download_state || song.state} />
                  </td>

                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '4px' }}>
                      {song.download_state !== 'DOWNLOADED' ? (
                        <button
                          onClick={() => handleDownload(song.id, song.title)}
                          className="btn-icon"
                          style={{ width: '30px', height: '30px', color: 'var(--accent-primary)' }}
                          title="Download song"
                          aria-label={`Download ${song.title}`}
                        >
                          <Download size={14} />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleOpenFolder(song.id)}
                          className="btn-icon"
                          style={{ width: '30px', height: '30px', color: 'var(--color-success)' }}
                          title="Reveal in Explorer"
                          aria-label="Reveal in Explorer"
                        >
                          <FolderOpen size={14} />
                        </button>
                      )}

                      <button
                        onClick={() => handleRemoveFavorite(song.id, song.title)}
                        className="btn-icon"
                        style={{ width: '30px', height: '30px', color: 'var(--color-error)' }}
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
    </div>
  );
};
