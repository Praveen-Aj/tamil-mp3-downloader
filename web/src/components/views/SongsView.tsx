import React, { useEffect, useState, useCallback } from 'react';
import {
  Search,
  Play,
  Download,
  Trash2,
  Heart,
  FolderOpen,
  Filter,
  ChevronLeft,
  ChevronRight,
  Music,
} from 'lucide-react';
import { songsApi, downloadsApi } from '../../api/endpoints';
import { Song } from '../../api/types';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { useApp } from '../../context/AppContext';
import { Button } from '../common/Button';
import { QualityBadge, StateBadge } from '../common/Badge';

export const SongsView: React.FC = () => {
  const { playSong } = useAudioPlayer();
  const { showToast, refreshStats } = useApp();

  const [songs, setSongs] = useState<Song[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [query, setQuery] = useState('');
  const [stateFilter, setStateFilter] = useState('ALL');
  const [loading, setLoading] = useState(false);

  const loadSongs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await songsApi.getSongs({
        query: query.trim(),
        state: stateFilter === 'ALL' ? undefined : stateFilter,
        page,
        page_size: pageSize,
      });

      if (res.success && res.data) {
        setSongs(res.data.items || []);
        setTotal(res.data.total || 0);
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to load songs', 'error');
    } finally {
      setLoading(false);
    }
  }, [query, stateFilter, page, pageSize, showToast]);

  useEffect(() => {
    loadSongs();
  }, [loadSongs]);

  const handleDownload = async (songId: number) => {
    try {
      const res = await downloadsApi.queueSongs([songId]);
      if (res.success) {
        showToast('Download queued successfully', 'success');
        refreshStats();
        loadSongs();
      }
    } catch (err: any) {
      showToast(err.message || 'Download failed to queue', 'error');
    }
  };

  const handleDelete = async (songId: number) => {
    if (!window.confirm('Are you sure you want to remove this song from library?')) return;
    try {
      await songsApi.deleteSong(songId, false, true);
      showToast('Song removed from library', 'info');
      refreshStats();
      loadSongs();
    } catch (err: any) {
      showToast(err.message || 'Failed to remove song', 'error');
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
      {/* Controls Bar */}
      <div
        className="glass-panel"
        style={{
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '16px',
          flexWrap: 'wrap',
        }}
      >
        {/* Search */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '6px 12px',
            gap: '8px',
            width: '280px',
          }}
        >
          <Search size={15} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Filter songs by title..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            style={{ flex: 1, fontSize: '13px' }}
          />
        </div>

        {/* State Filter Buttons */}
        <div style={{ display: 'flex', gap: '6px' }}>
          {(['ALL', 'OWNED', 'NEW'] as const).map((st) => (
            <button
              key={st}
              onClick={() => {
                setStateFilter(st);
                setPage(1);
              }}
              className={`btn ${stateFilter === st ? 'btn-primary' : 'btn-secondary'}`}
              style={{ padding: '6px 12px', fontSize: '12px' }}
            >
              {st === 'ALL' ? 'All Songs' : st === 'OWNED' ? 'Downloaded' : 'Available'}
            </button>
          ))}
        </div>
      </div>

      {/* Songs Table */}
      <div className="glass-panel" style={{ overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '50px' }}>Play</th>
              <th>Title</th>
              <th>Artist</th>
              <th>Album</th>
              <th>Year</th>
              <th>Quality</th>
              <th>Status</th>
              <th style={{ textAlign: 'right', width: '120px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  Loading library tracks...
                </td>
              </tr>
            ) : songs.length === 0 ? (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No songs matching criteria found.
                </td>
              </tr>
            ) : (
              songs.map((song) => (
                <tr key={song.id}>
                  <td>
                    <button
                      onClick={() => playSong(song)}
                      className="btn-icon"
                      style={{ width: '32px', height: '32px' }}
                      title="Play stream"
                    >
                      <Play size={14} fill="currentColor" />
                    </button>
                  </td>
                  <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{song.title}</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{song.artist || '—'}</td>
                  <td style={{ color: 'var(--text-secondary)' }}>{song.album || '—'}</td>
                  <td style={{ color: 'var(--text-muted)' }}>{song.year || '—'}</td>
                  <td>
                    <QualityBadge quality={song.quality} />
                  </td>
                  <td>
                    <StateBadge state={song.state} />
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'inline-flex', gap: '4px' }}>
                      {song.state !== 'OWNED' ? (
                        <button
                          onClick={() => handleDownload(song.id)}
                          className="btn-icon"
                          style={{ width: '30px', height: '30px', color: 'var(--accent-primary)' }}
                          title="Download track"
                        >
                          <Download size={14} />
                        </button>
                      ) : (
                        <button
                          onClick={() => handleOpenFolder(song.id)}
                          className="btn-icon"
                          style={{ width: '30px', height: '30px', color: 'var(--color-success)' }}
                          title="Reveal in Explorer"
                        >
                          <FolderOpen size={14} />
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(song.id)}
                        className="btn-icon"
                        style={{ width: '30px', height: '30px', color: 'var(--color-error)' }}
                        title="Delete song"
                      >
                        <Trash2 size={14} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>

        {/* Pagination Footer */}
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
            Showing {songs.length} of {total} songs (Page {page} of {totalPages})
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
      </div>
    </div>
  );
};
