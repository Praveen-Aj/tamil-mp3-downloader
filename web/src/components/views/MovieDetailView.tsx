import React, { useEffect, useState } from 'react';
import { ArrowLeft, Play, Download, Music, Film, CheckCircle2 } from 'lucide-react';
import { moviesApi, downloadsApi } from '../../api/endpoints';
import { Movie, Song } from '../../api/types';
import { useApp } from '../../context/AppContext';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { Button } from '../common/Button';
import { QualityBadge, StateBadge } from '../common/Badge';
import { api } from '../../api/client';

export const MovieDetailView: React.FC = () => {
  const { selectedEntityId, navigateTo, showToast, refreshStats } = useApp();
  const { playSong } = useAudioPlayer();

  const [movie, setMovie] = useState<Movie | null>(null);
  const [songs, setSongs] = useState<Song[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!selectedEntityId) return;
    const loadDetails = async () => {
      setLoading(true);
      try {
        const res = await moviesApi.getMovieSongs(Number(selectedEntityId));
        if (res.success && res.data) {
          setMovie(res.data.movie);
          setSongs(res.data.songs || []);
        }
      } catch (err: any) {
        showToast(err.message || 'Failed to load movie details', 'error');
      } finally {
        setLoading(false);
      }
    };
    loadDetails();
  }, [selectedEntityId, showToast]);

  const handleDownloadAll = async () => {
    if (!selectedEntityId || !movie) return;
    try {
      const res = await moviesApi.startDownload(Number(selectedEntityId));
      if (res.success) {
        showToast(`Queued ${res.data.queued_count} songs from "${movie.title}"`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue download', 'error');
    }
  };

  const handleDownloadSong = async (songId: number) => {
    try {
      const res = await downloadsApi.queueSongs([songId]);
      if (res.success) {
        showToast('Song queued for download', 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to download song', 'error');
    }
  };

  if (!selectedEntityId || (!loading && !movie)) {
    return (
      <div style={{ padding: '32px' }}>
        <Button variant="ghost" onClick={() => navigateTo('movies')}>
          <ArrowLeft size={16} /> Back to Movies
        </Button>
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          Movie not found.
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '28px' }}>
      <Button variant="ghost" onClick={() => navigateTo('movies')} style={{ alignSelf: 'flex-start' }}>
        <ArrowLeft size={16} /> Back to Soundtracks
      </Button>

      {/* Hero Movie Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '28px 32px',
          display: 'flex',
          gap: '28px',
          alignItems: 'center',
          flexWrap: 'wrap',
          background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.4) 0%, rgba(17, 26, 46, 0.8) 100%)',
        }}
      >
        <img
          src={api.getArtworkUrl('movie', Number(selectedEntityId), 180, 180)}
          alt={movie?.title}
          style={{
            width: '140px',
            height: '140px',
            borderRadius: 'var(--radius-md)',
            objectFit: 'cover',
            boxShadow: 'var(--shadow-lg)',
            backgroundColor: 'var(--bg-surface-active)',
          }}
          onError={(e) => {
            (e.target as HTMLImageElement).src =
              'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="140" height="140" fill="%231e1b4b"><rect width="140" height="140"/></svg>';
          }}
        />

        <div style={{ flex: 1, minWidth: '240px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--accent-secondary)', fontSize: '13px', fontWeight: 600 }}>
            <Film size={15} /> ORIGINAL SOUNDTRACK
          </div>
          <h2 className="title-display" style={{ fontSize: '32px', fontWeight: 800, marginTop: '4px' }}>
            {movie?.title}
          </h2>
          <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '6px' }}>
            {movie?.year ? `Released in ${movie.year}` : ''} • {songs.length} Tracks
          </div>

          <div style={{ marginTop: '16px' }}>
            <Button variant="primary" onClick={handleDownloadAll}>
              <Download size={16} /> Download Complete Album
            </Button>
          </div>
        </div>
      </div>

      {/* Tracklist Table */}
      <div className="glass-panel" style={{ overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '50px' }}>Play</th>
              <th>Track Title</th>
              <th>Artist</th>
              <th>Quality</th>
              <th>Status</th>
              <th style={{ textAlign: 'right', width: '100px' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {songs.map((song) => (
              <tr key={song.id}>
                <td>
                  <button
                    onClick={() => playSong(song)}
                    className="btn-icon"
                    style={{ width: '32px', height: '32px' }}
                    title="Play track"
                  >
                    <Play size={14} fill="currentColor" />
                  </button>
                </td>
                <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{song.title}</td>
                <td style={{ color: 'var(--text-secondary)' }}>{song.artist || '—'}</td>
                <td>
                  <QualityBadge quality={song.quality} />
                </td>
                <td>
                  <StateBadge state={song.state} />
                </td>
                <td style={{ textAlign: 'right' }}>
                  {song.state !== 'OWNED' ? (
                    <Button size="sm" variant="secondary" onClick={() => handleDownloadSong(song.id)}>
                      <Download size={13} />
                    </Button>
                  ) : (
                    <span style={{ color: 'var(--color-success)', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <CheckCircle2 size={14} /> Saved
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
