import React, { useEffect, useState } from 'react';
import { ArrowLeft, Play, Pause, Download, Music, Film, CheckCircle2, Clock, Sparkles } from 'lucide-react';
import { moviesApi, downloadsApi } from '../../api/endpoints';
import { Movie, Song } from '../../api/types';
import { useApp } from '../../context/AppContext';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { Button } from '../common/Button';
import { QualityBadge, StateBadge } from '../common/Badge';
import { api } from '../../api/client';

export const MovieDetailView: React.FC = () => {
  const { selectedEntityId, navigateTo, showToast, refreshStats } = useApp();
  const { playSong, currentSong, isPlaying } = useAudioPlayer();

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
        // Refresh local details
        const refreshed = await moviesApi.getMovieSongs(Number(selectedEntityId));
        if (refreshed.success && refreshed.data) {
          setSongs(refreshed.data.songs || []);
        }
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue download', 'error');
    }
  };

  const handleDownloadMissing = async () => {
    if (!selectedEntityId || !movie) return;
    const missing = songs.filter(s => !s.has_file && s.state !== 'OWNED');
    if (missing.length === 0) {
      showToast('All songs are already downloaded in high quality!', 'info');
      return;
    }
    try {
      const res = await downloadsApi.queueSongs(missing.map(s => s.id));
      if (res.success) {
        showToast(`Queued ${missing.length} missing songs for download`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue missing tracks', 'error');
    }
  };

  const handleDownloadSong = async (songId: number, title: string) => {
    try {
      const res = await downloadsApi.queueSongs([songId]);
      if (res.success) {
        showToast(`Queued "${title}" for download`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to download song', 'error');
    }
  };

  const handlePlayAll = () => {
    const playable = songs.filter(s => s.has_file || s.file_path || s.state === 'OWNED');
    if (playable.length > 0) {
      playSong(playable[0], playable);
      showToast(`Playing soundtrack: ${movie?.title}`, 'info');
    } else {
      showToast('Download tracks first to enable audio streaming', 'warning');
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '—';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  if (!selectedEntityId || (!loading && !movie)) {
    return (
      <div style={{ padding: '32px' }}>
        <Button variant="ghost" onClick={() => navigateTo('movies')}>
          <ArrowLeft size={16} /> Back to Movies
        </Button>
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          Soundtrack album not found.
        </div>
      </div>
    );
  }

  const downloadedCount = songs.filter(s => s.has_file || s.state === 'OWNED').length;
  const missingCount = Math.max(0, songs.length - downloadedCount);
  const isComplete = songs.length > 0 && downloadedCount >= songs.length;

  return (
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '32px' }}>
      <Button variant="ghost" onClick={() => navigateTo('movies')} style={{ alignSelf: 'flex-start' }}>
        <ArrowLeft size={16} /> Back to Soundtracks & Movies
      </Button>

      {/* 1. Cinematic Hero Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '36px',
          display: 'flex',
          gap: '32px',
          alignItems: 'center',
          flexWrap: 'wrap',
          background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.95) 100%)',
          position: 'relative',
          overflow: 'hidden',
          borderRadius: 'var(--radius-xl)',
        }}
      >
        {/* Large 2:3 Vertical Movie Poster */}
        <div
          style={{
            width: '180px',
            aspectRatio: '2 / 3',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
            boxShadow: '0 16px 36px rgba(0, 0, 0, 0.65)',
            backgroundColor: '#0f172a',
            flexShrink: 0,
            border: '1px solid rgba(255, 255, 255, 0.1)',
          }}
        >
          <img
            src={api.getArtworkUrl('movie', Number(selectedEntityId), 400, 600)}
            alt={movie?.title}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onError={(e) => {
              (e.target as HTMLImageElement).src =
                'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="450" fill="%230f172a"><rect width="300" height="450"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%236366f1" font-size="36">🎬</text></svg>';
            }}
          />
        </div>

        {/* Hero Metadata & Actions */}
        <div style={{ flex: 1, minWidth: '280px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', color: 'var(--accent-secondary)', fontSize: '13px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
            <Film size={15} /> ORIGINAL MOTION PICTURE SOUNDTRACK
          </div>

          <h1 className="title-display" style={{ fontSize: '36px', fontWeight: 800, marginTop: '8px', marginBottom: '8px', color: '#f8fafc' }}>
            {movie?.title}
          </h1>

          <div style={{ fontSize: '14px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap', marginTop: '4px', marginBottom: '20px' }}>
            {movie?.year && (
              <span style={{ backgroundColor: 'rgba(255, 255, 255, 0.08)', padding: '2px 8px', borderRadius: 'var(--radius-xs)', color: '#f8fafc', fontWeight: 600 }}>
                {movie.year}
              </span>
            )}
            <span>{songs.length} Tracks</span>
            <span>•</span>
            <span style={{ color: isComplete ? 'var(--color-success)' : 'var(--text-secondary)' }}>
              {downloadedCount} Downloaded {isComplete ? '(Complete Album)' : `(${missingCount} Missing)`}
            </span>
          </div>

          {/* Action Bar */}
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
            <Button variant="primary" onClick={handlePlayAll} style={{ padding: '10px 20px', gap: '8px' }}>
              <Play size={16} fill="currentColor" /> Play Soundtrack
            </Button>

            {missingCount > 0 && (
              <Button variant="secondary" onClick={handleDownloadMissing} style={{ padding: '10px 20px', gap: '8px' }}>
                <Download size={16} color="var(--accent-primary)" /> Download Missing ({missingCount})
              </Button>
            )}

            <Button variant="ghost" onClick={handleDownloadAll} style={{ padding: '10px 18px', gap: '8px' }}>
              <Download size={15} /> Download All Tracks
            </Button>
          </div>
        </div>
      </div>

      {/* 2. Tracklist Section */}
      <div className="glass-panel" style={{ overflow: 'hidden', borderRadius: 'var(--radius-lg)' }}>
        <div style={{ padding: '20px 24px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
            Tracklist ({songs.length} Songs)
          </h3>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            High-fidelity 320 kbps stream & download
          </span>
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '48px', textAlign: 'center' }}>#</th>
              <th style={{ width: '48px' }}>Play</th>
              <th style={{ width: '56px' }}>Art</th>
              <th>Track Title</th>
              <th>Artists</th>
              <th style={{ width: '80px' }}>Duration</th>
              <th>Quality</th>
              <th>Status</th>
              <th style={{ textAlign: 'right', width: '120px' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {songs.map((song, index) => {
              const isCurrentlyPlaying = currentSong?.id === song.id && isPlaying;
              const isDownloaded = song.has_file || song.state === 'OWNED';

              return (
                <tr
                  key={song.id}
                  style={{
                    backgroundColor: currentSong?.id === song.id ? 'rgba(99, 102, 241, 0.08)' : undefined,
                  }}
                >
                  {/* Track Number */}
                  <td style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px', fontWeight: 600 }}>
                    {index + 1}
                  </td>

                  {/* Play Button */}
                  <td>
                    <button
                      onClick={() => playSong(song, songs)}
                      className="btn-icon"
                      style={{
                        width: '32px',
                        height: '32px',
                        color: isCurrentlyPlaying ? 'var(--accent-primary)' : 'var(--text-primary)',
                      }}
                      title={isCurrentlyPlaying ? 'Pause' : 'Play track'}
                    >
                      {isCurrentlyPlaying ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
                    </button>
                  </td>

                  {/* 40x40 Artwork Thumbnail */}
                  <td>
                    <img
                      src={api.getArtworkUrl('song', song.id, 80, 80)}
                      alt={song.title}
                      style={{
                        width: '38px',
                        height: '38px',
                        borderRadius: 'var(--radius-sm)',
                        objectFit: 'cover',
                        backgroundColor: '#1e293b',
                      }}
                      loading="lazy"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src =
                          'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="38" height="38" fill="%231e293b"><rect width="38" height="38"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%2364748b" font-size="14">🎵</text></svg>';
                      }}
                    />
                  </td>

                  {/* Title */}
                  <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    {song.title}
                  </td>

                  {/* Artists */}
                  <td style={{ color: 'var(--text-secondary)' }}>
                    {song.artist || '—'}
                  </td>

                  {/* Duration */}
                  <td style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                    {formatDuration(song.duration_sec)}
                  </td>

                  {/* Quality Badge */}
                  <td>
                    <QualityBadge quality={song.quality} isDownloaded={isDownloaded} />
                  </td>

                  {/* Download State Badge */}
                  <td>
                    <StateBadge state={song.state} downloadState={song.download_state} canUpgrade={song.can_upgrade} />
                  </td>

                  {/* Action */}
                  <td style={{ textAlign: 'right' }}>
                    {!isDownloaded ? (
                      <button
                        onClick={() => handleDownloadSong(song.id, song.title)}
                        className="btn-icon"
                        style={{ width: '32px', height: '32px', color: 'var(--accent-primary)' }}
                        title="Download track"
                      >
                        <Download size={14} />
                      </button>
                    ) : (
                      <span style={{ color: 'var(--color-success)', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
                        <CheckCircle2 size={13} /> Ready
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
