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
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '28px' }}>
      <Button variant="ghost" onClick={() => navigateTo('movies')} style={{ alignSelf: 'flex-start', padding: '6px 12px', fontSize: '13px' }}>
        <ArrowLeft size={15} /> Movies
      </Button>

      {/* 1. Cinematic Hero Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '28px 32px',
          display: 'flex',
          gap: '28px',
          alignItems: 'center',
          flexWrap: 'wrap',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
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
            boxShadow: '0 12px 28px rgba(0, 0, 0, 0.55)',
            backgroundColor: '#16161a',
            flexShrink: 0,
            border: '1px solid var(--border-subtle)',
          }}
        >
          <img
            src={api.getArtworkUrl('movie', Number(selectedEntityId), 400, 600)}
            alt={movie?.title}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            onError={(e) => {
              (e.target as HTMLImageElement).src =
                'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="450" fill="%2316161a"><rect width="300" height="450"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%238B7CF8" font-size="36">🎬</text></svg>';
            }}
          />
        </div>

        {/* Hero Metadata & Actions */}
        <div style={{ flex: 1, minWidth: '280px', display: 'flex', flexDirection: 'column' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: 'var(--accent-secondary)', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em' }}>
            <Film size={14} /> Original Motion Picture Soundtrack
          </div>

          <h1 className="title-display" style={{ fontSize: '32px', fontWeight: 800, marginTop: '6px', marginBottom: '8px', color: '#f8fafc', letterSpacing: '-0.02em' }}>
            {movie?.title}
          </h1>

          <div style={{ fontSize: '13px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap', marginTop: '2px', marginBottom: '20px' }}>
            {movie?.year && (
              <span style={{ backgroundColor: 'rgba(255, 255, 255, 0.08)', padding: '2px 8px', borderRadius: 'var(--radius-xs)', color: '#f8fafc', fontWeight: 600 }}>
                {movie.year}
              </span>
            )}
            <span>{songs.length} Tracks</span>
            <span>·</span>
            <span style={{ color: isComplete ? 'var(--color-success)' : 'var(--text-secondary)' }}>
              {downloadedCount} Downloaded {isComplete ? '(Complete Album)' : `(${missingCount} Missing)`}
            </span>
          </div>

          {/* Action Bar */}
          <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap' }}>
            <Button variant="primary" onClick={handlePlayAll} style={{ padding: '9px 18px', gap: '8px', fontSize: '13px' }}>
              <Play size={15} fill="currentColor" /> Play Soundtrack
            </Button>

            {missingCount > 0 && (
              <Button variant="secondary" onClick={handleDownloadMissing} style={{ padding: '9px 18px', gap: '8px', fontSize: '13px' }}>
                <Download size={15} color="var(--accent-primary)" /> Download Missing ({missingCount})
              </Button>
            )}

            <Button variant="ghost" onClick={handleDownloadAll} style={{ padding: '9px 16px', gap: '8px', fontSize: '13px' }}>
              <Download size={14} /> Download All
            </Button>
          </div>
        </div>
      </div>

      {/* 2. Tracklist Section */}
      <div className="glass-panel" style={{ overflow: 'hidden', borderRadius: 'var(--radius-lg)' }}>
        <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
            Soundtrack Tracks ({songs.length})
          </h3>
          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            320 kbps high-fidelity stream & download
          </span>
        </div>

        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '44px', textAlign: 'center' }}>#</th>
              <th>Track</th>
              <th style={{ width: '75px' }}>Duration</th>
              <th style={{ width: '90px' }}>Quality</th>
              <th style={{ width: '115px' }}>Status</th>
              <th style={{ textAlign: 'right', width: '100px' }}>Action</th>
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
                    backgroundColor: currentSong?.id === song.id ? 'rgba(139, 124, 248, 0.08)' : undefined,
                  }}
                >
                  {/* Track Number */}
                  <td style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px', fontWeight: 600 }}>
                    {index + 1}
                  </td>

                  {/* Track: Artwork with play overlay + Title + Artist */}
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
                          backgroundColor: '#16161a',
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
                              'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" fill="%2316161a"><rect width="40" height="40"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%238B7CF8" font-size="14">🎵</text></svg>';
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
                            opacity: isCurrentlyPlaying ? 1 : 0,
                            transition: 'opacity 150ms ease',
                          }}
                          className="play-overlay"
                        >
                          {isCurrentlyPlaying ? <Pause size={14} fill="currentColor" /> : <Play size={14} fill="currentColor" />}
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

                  {/* Duration */}
                  <td style={{ color: 'var(--text-muted)', fontSize: '12px', fontVariantNumeric: 'tabular-nums' }}>
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
                        style={{ width: '30px', height: '30px', color: 'var(--accent-primary)' }}
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
