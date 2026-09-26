import React, { useEffect, useState } from 'react';
import {
  Music,
  CheckCircle2,
  Film,
  Users,
  HardDrive,
  Flame,
  ArrowDownCircle,
  Play,
  FolderOpen,
  Sparkles,
  AlertTriangle,
  Download,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { DownloadStateBadge, QualityBadge } from '../common/Badge';
import { songsApi, moviesApi, artistsApi, downloadsApi } from '../../api/endpoints';
import { Song, Movie, Artist } from '../../api/types';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { api } from '../../api/client';

export const DashboardView: React.FC = () => {
  const { stats, navigateTo, showToast, refreshStats } = useApp();
  const { playSong } = useAudioPlayer();

  const [downloadedSongs, setDownloadedSongs] = useState<Song[]>([]);
  const [missingSongs, setMissingSongs] = useState<Song[]>([]);
  const [featuredMovies, setFeaturedMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(true);
  const [queuingMissing, setQueuingMissing] = useState(false);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const [downloadedRes, missingRes, moviesRes] = await Promise.all([
          songsApi.getSongs({ state: 'OWNED', page_size: 6, sort_by: 'id', sort_order: 'desc' }),
          songsApi.getSongs({ state: 'NEW', page_size: 6, sort_by: 'id', sort_order: 'desc' }),
          moviesApi.getMovies({ page_size: 4, sort_by: 'id', sort_order: 'desc' }),
        ]);

        if (downloadedRes.success && downloadedRes.data) {
          setDownloadedSongs(downloadedRes.data.items || []);
        }
        if (missingRes.success && missingRes.data) {
          setMissingSongs(missingRes.data.items || []);
        }
        if (featuredMovies.length === 0 && moviesRes.success && moviesRes.data) {
          setFeaturedMovies(moviesRes.data.items || []);
        }
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    loadDashboard();
  }, []);

  const handleDownloadAllMissing = async () => {
    setQueuingMissing(true);
    try {
      const res = await songsApi.downloadMissingSongs(320);
      if (res.success && res.data) {
        showToast(
          `Queued ${res.data.queued_count} missing songs for download in high quality (320 kbps)`,
          'success'
        );
        refreshStats();
        // Refresh missing list
        const missingRes = await songsApi.getSongs({ state: 'NEW', page_size: 6 });
        if (missingRes.success && missingRes.data) {
          setMissingSongs(missingRes.data.items || []);
        }
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue missing songs', 'error');
    } finally {
      setQueuingMissing(false);
    }
  };

  const handleDownloadSingle = async (songId: number, title: string) => {
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

  const handleOpenFolder = async (songId: number) => {
    try {
      await songsApi.openFolder(songId);
    } catch (err: any) {
      showToast(err.message || 'Failed to open file folder', 'error');
    }
  };

  const formatBytes = (bytes?: number) => {
    if (!bytes) return '0 MB';
    const mb = bytes / (1024 * 1024);
    if (mb > 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${Math.round(mb)} MB`;
  };

  const missingCount = Math.max(0, (stats?.total_songs ?? 0) - (stats?.total_owned ?? 0));

  return (
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {/* 1. Hero Listening & Discovery Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '32px',
          background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.7) 0%, rgba(15, 23, 42, 0.85) 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        <div style={{ zIndex: 2, maxWidth: '640px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: 'var(--accent-secondary)', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '8px' }}>
            <Sparkles size={14} /> Personal Music Studio
          </div>
          <h2 className="title-display text-gradient" style={{ fontSize: '28px', fontWeight: 800, margin: 0 }}>
            Your Tamil Soundtrack Library
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: '8px', fontSize: '14px', lineHeight: 1.5 }}>
            High-fidelity canonical music library with verified physical storage, automatic multi-source deduplication, and lossless ID3 tag preservation.
          </p>
          <div style={{ display: 'flex', gap: '12px', marginTop: '20px' }}>
            <Button
              variant="primary"
              onClick={() => {
                if (downloadedSongs.length > 0) {
                  playSong(downloadedSongs[0], downloadedSongs);
                } else {
                  navigateTo('songs');
                }
              }}
              aria-label="Quick Play Library"
            >
              <Play size={16} fill="currentColor" /> Quick Listening
            </Button>
            <Button variant="secondary" onClick={() => navigateTo('songs')} aria-label="Browse All Songs">
              <Music size={16} /> Browse Songs
            </Button>
            {missingCount > 0 && (
              <Button
                variant="secondary"
                onClick={handleDownloadAllMissing}
                loading={queuingMissing}
                aria-label="Download All Missing Tracks"
                style={{ borderColor: 'var(--accent-primary)', color: 'var(--accent-primary)' }}
              >
                <Download size={16} /> Download Missing ({missingCount})
              </Button>
            )}
          </div>
        </div>

        {/* Quick Picks Mini-Cards */}
        {downloadedSongs.length > 0 && (
          <div
            style={{
              zIndex: 2,
              display: 'flex',
              flexDirection: 'column',
              gap: '8px',
              width: '280px',
              backgroundColor: 'rgba(0, 0, 0, 0.25)',
              padding: '12px',
              borderRadius: 'var(--radius-lg)',
              border: '1px solid var(--border-subtle)',
            }}
          >
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
              Quick Picks • Ready to Play
            </div>
            {downloadedSongs.slice(0, 3).map((song) => (
              <div
                key={song.id}
                onClick={() => playSong(song, downloadedSongs)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '10px',
                  padding: '6px 8px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'rgba(255, 255, 255, 0.03)',
                  cursor: 'pointer',
                  transition: 'background var(--transition-fast)',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.08)')}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.03)')}
              >
                <img
                  src={api.getArtworkUrl('song', song.id, 40, 40)}
                  alt={song.title}
                  style={{ width: '34px', height: '34px', borderRadius: '4px', objectFit: 'cover' }}
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="34" height="34" fill="%231e293b"><rect width="34" height="34"/></svg>';
                  }}
                />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {song.title}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {song.artist || song.album || 'Unknown'}
                  </div>
                </div>
                <Play size={13} color="var(--accent-primary)" fill="currentColor" />
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 2. Key Metrics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px' }}>
        <Card onClick={() => navigateTo('songs')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Total Songs</span>
            <Music size={18} color="var(--accent-primary)" />
          </div>
          <div className="title-display" style={{ fontSize: '28px', marginTop: '10px' }}>
            {stats?.total_songs ?? 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Canonical tracks cataloged
          </div>
        </Card>

        <Card onClick={() => navigateTo('songs')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Downloaded</span>
            <CheckCircle2 size={18} color="var(--color-success)" />
          </div>
          <div className="title-display" style={{ fontSize: '28px', marginTop: '10px', color: 'var(--color-success)' }}>
            {stats?.total_owned ?? 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Available offline on disk
          </div>
        </Card>

        <Card onClick={() => navigateTo('songs')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Missing Tracks</span>
            <AlertTriangle size={18} color="var(--color-warning)" />
          </div>
          <div className="title-display" style={{ fontSize: '28px', marginTop: '10px', color: missingCount > 0 ? 'var(--color-warning)' : 'var(--text-primary)' }}>
            {missingCount}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Ready to be queued
          </div>
        </Card>

        <Card onClick={() => navigateTo('movies')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Soundtracks</span>
            <Film size={18} color="var(--accent-secondary)" />
          </div>
          <div className="title-display" style={{ fontSize: '28px', marginTop: '10px' }}>
            {stats?.total_movies ?? 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Movie albums cataloged
          </div>
        </Card>

        <Card onClick={() => navigateTo('artists')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Artists</span>
            <Users size={18} color="#f59e0b" />
          </div>
          <div className="title-display" style={{ fontSize: '28px', marginTop: '10px' }}>
            {stats?.total_artists ?? 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Singers, lyricists, composers
          </div>
        </Card>

        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Storage</span>
            <HardDrive size={18} color="#10b981" />
          </div>
          <div className="title-display" style={{ fontSize: '28px', marginTop: '10px' }}>
            {formatBytes(stats?.total_storage_bytes)}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Verified audio size
          </div>
        </Card>
      </div>

      {/* 3. Two Columns: Recently Downloaded Songs & Missing Tracks */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
        {/* Recently Downloaded Songs */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={18} color="var(--color-success)" />
              <h3 className="title-display" style={{ fontSize: '16px' }}>Recently Downloaded</h3>
            </div>
            <Button variant="ghost" size="sm" onClick={() => navigateTo('songs')}>
              View All
            </Button>
          </div>

          {downloadedSongs.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', padding: '32px 0', textAlign: 'center', fontSize: '13px' }}>
              No downloaded songs yet. Queue a song or movie to start downloading!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {downloadedSongs.map((s) => (
                <div
                  key={s.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-subtle)',
                    transition: 'all var(--transition-fast)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.02)')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
                    <button
                      onClick={() => playSong(s, downloadedSongs)}
                      className="btn-icon"
                      style={{ width: '32px', height: '32px', flexShrink: 0, backgroundColor: 'rgba(255, 255, 255, 0.06)' }}
                      title="Play track"
                      aria-label={`Play ${s.title}`}
                    >
                      <Play size={13} fill="currentColor" />
                    </button>
                    <img
                      src={api.getArtworkUrl('song', s.id, 40, 40)}
                      alt={s.title}
                      style={{ width: '32px', height: '32px', borderRadius: '4px', objectFit: 'cover', flexShrink: 0 }}
                      onError={(e) => {
                        (e.target as HTMLImageElement).src =
                          'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="%231e293b"><rect width="32" height="32"/></svg>';
                      }}
                    />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: '13px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {s.title}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {s.artist || s.album || 'Unknown'} {s.year ? `• ${s.year}` : ''}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                    <QualityBadge quality={s.quality} />
                    <button
                      onClick={() => handleOpenFolder(s.id)}
                      className="btn-icon"
                      style={{ width: '28px', height: '28px', color: 'var(--color-success)' }}
                      title="Reveal in Explorer"
                      aria-label="Open folder"
                    >
                      <FolderOpen size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Missing Tracks in Collection */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', flexWrap: 'wrap', gap: '12px', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ArrowDownCircle size={18} color="var(--accent-primary)" />
              <h3 className="title-display" style={{ fontSize: '16px', margin: 0 }}>Missing in Library</h3>
            </div>
            {missingCount > 0 && (
              <Button
                variant="primary"
                size="sm"
                onClick={handleDownloadAllMissing}
                loading={queuingMissing}
                aria-label="Download All Missing"
              >
                <Download size={13} /> Download All ({missingCount})
              </Button>
            )}
          </div>

          {missingSongs.length === 0 ? (
            <div style={{ color: 'var(--color-success)', padding: '32px 0', textAlign: 'center', fontSize: '13px' }}>
              ✓ All cataloged songs are downloaded to your physical library!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {missingSongs.map((s) => (
                <div
                  key={s.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '8px 12px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
                    <img
                      src={api.getArtworkUrl('song', s.id, 40, 40)}
                      alt={s.title}
                      style={{ width: '32px', height: '32px', borderRadius: '4px', objectFit: 'cover', flexShrink: 0 }}
                      onError={(e) => {
                        (e.target as HTMLImageElement).src =
                          'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="%231e293b"><rect width="32" height="32"/></svg>';
                      }}
                    />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: '13px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {s.title}
                      </div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {s.artist || s.album || 'Unknown'} {s.year ? `• ${s.year}` : ''}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                    <DownloadStateBadge state={s.download_state || 'NOT_DOWNLOADED'} />
                    <button
                      onClick={() => handleDownloadSingle(s.id, s.title)}
                      className="btn-icon"
                      style={{ width: '28px', height: '28px', color: 'var(--accent-primary)' }}
                      title="Download song"
                      aria-label={`Download ${s.title}`}
                    >
                      <Download size={14} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 4. Featured Soundtrack Albums */}
      {featuredMovies.length > 0 && (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Film size={18} color="var(--accent-secondary)" />
              <h3 className="title-display" style={{ fontSize: '18px' }}>Soundtrack Collections</h3>
            </div>
            <Button variant="ghost" size="sm" onClick={() => navigateTo('movies')}>
              Explore All Movies
            </Button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))', gap: '16px' }}>
            {featuredMovies.map((movie) => (
              <Card
                key={movie.id}
                onClick={() => navigateTo('movie_detail', movie.id)}
                className="glass-card"
                style={{ display: 'flex', alignItems: 'center', gap: '14px', padding: '12px' }}
              >
                <img
                  src={api.getArtworkUrl('movie', movie.id, 80, 80)}
                  alt={movie.title || movie.name}
                  style={{ width: '56px', height: '56px', borderRadius: '8px', objectFit: 'cover', flexShrink: 0 }}
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" fill="%231e1b4b"><rect width="56" height="56"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23fff" font-size="18">🎬</text></svg>';
                  }}
                />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontWeight: 700, fontSize: '13px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {movie.title || movie.name}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {movie.year || 'OST'} • {movie.total_songs ?? 0} tracks
                  </div>
                </div>
              </Card>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
