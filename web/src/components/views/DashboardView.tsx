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
  Download,
  ChevronRight,
  Heart,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
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
  const [topArtists, setTopArtists] = useState<Artist[]>([]);
  const [loading, setLoading] = useState(true);
  const [queuingMissing, setQueuingMissing] = useState(false);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const [downloadedRes, missingRes, moviesRes, artistsRes] = await Promise.all([
          songsApi.getSongs({ state: 'OWNED', page_size: 6, sort_by: 'id', sort_order: 'desc' }),
          songsApi.getSongs({ state: 'NEW', page_size: 6, sort_by: 'id', sort_order: 'desc' }),
          moviesApi.getMovies({ page_size: 5, sort_by: 'track_count', sort_order: 'desc' }),
          artistsApi.getArtists({ page_size: 6 }),
        ]);

        if (downloadedRes.success && downloadedRes.data) {
          setDownloadedSongs(downloadedRes.data.items || []);
        }
        if (missingRes.success && missingRes.data) {
          setMissingSongs(missingRes.data.items || []);
        }
        if (moviesRes.success && moviesRes.data) {
          setFeaturedMovies(moviesRes.data.items || []);
        }
        if (artistsRes.success && artistsRes.data) {
          setTopArtists(artistsRes.data.items || []);
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

  const formatBytes = (bytes?: number) => {
    if (!bytes) return '0 MB';
    const mb = bytes / (1024 * 1024);
    if (mb > 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${Math.round(mb)} MB`;
  };

  const missingCount = Math.max(0, (stats?.total_songs ?? 0) - (stats?.total_owned ?? 0));

  return (
    <div className="view-container" style={{ gap: '30px' }}>
      {/* 1. Music Library Hero Header */}
      <div
        className="glass-panel"
        style={{
          padding: '24px 28px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '20px',
          borderRadius: 'var(--radius-xl)',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
        }}
      >
        <div style={{ maxWidth: '640px' }}>
          <h1 className="title-display" style={{ fontSize: '26px', fontWeight: 700, margin: 0, color: 'var(--text-primary)', letterSpacing: '-0.02em' }}>
            Tamil Music Library
          </h1>
          <p style={{ color: 'var(--text-secondary)', marginTop: '6px', fontSize: '13.5px', marginBottom: '16px' }}>
            Personal collection of Tamil soundtracks, high-fidelity lossless & 320 kbps MP3s.
          </p>

          {/* Minimalist Library Stats Row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap', fontSize: '12.5px', color: 'var(--text-muted)' }}>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: 'var(--color-success)', fontWeight: 600 }}>
              <CheckCircle2 size={14} /> <span style={{ fontVariantNumeric: 'tabular-nums' }}>{stats?.total_owned ?? 0}</span> Downloaded
            </span>
            <span>·</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: 'var(--text-primary)' }}>
              <Film size={14} color="var(--accent-secondary)" /> <span style={{ fontVariantNumeric: 'tabular-nums' }}>{stats?.total_movies ?? 0}</span> Soundtracks
            </span>
            <span>·</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: 'var(--text-primary)' }}>
              <Music size={14} color="var(--accent-primary)" /> <span style={{ fontVariantNumeric: 'tabular-nums' }}>{stats?.total_songs ?? 0}</span> Tracks
            </span>
            <span>·</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: 'var(--text-primary)' }}>
              <HardDrive size={13} color="#f59e0b" /> <span style={{ fontVariantNumeric: 'tabular-nums' }}>{formatBytes(stats?.total_storage_bytes)}</span>
            </span>
          </div>
        </div>

        {/* Quick Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
          {missingCount > 0 && (
            <Button
              variant="primary"
              onClick={handleDownloadAllMissing}
              disabled={queuingMissing}
              style={{ padding: '10px 20px', gap: '8px', fontSize: '13px', fontWeight: 600 }}
            >
              <Download size={15} /> Download Missing ({missingCount})
            </Button>
          )}
          <Button
            variant="secondary"
            onClick={() => navigateTo('movies')}
            style={{ padding: '10px 18px', gap: '8px', fontSize: '13px' }}
          >
            <Film size={14} /> Browse Soundtracks
          </Button>
        </div>
      </div>

      {/* 2. Recently Downloaded Shelf */}
      {downloadedSongs.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={17} color="var(--color-success)" />
              <h2 style={{ fontSize: '17px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Recently Downloaded
              </h2>
            </div>
            <button
              onClick={() => navigateTo('songs')}
              style={{ background: 'none', border: 'none', color: 'var(--accent-primary)', fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
            >
              All Songs <ChevronRight size={14} />
            </button>
          </div>

          <div
            className="grid-responsive"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(175px, 1fr))',
              gap: '16px',
            }}
          >
            {downloadedSongs.map((song) => (
              <div
                key={song.id}
                onClick={() => playSong(song, downloadedSongs)}
                className="poster-card"
              >
                <div className="poster-img-wrap">
                  <img
                    src={api.getArtworkUrl('song', song.id, 240, 240)}
                    alt={song.title}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" fill="%2316161a"><rect width="200" height="200"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%238B7CF8" font-size="24">🎵</text></svg>';
                    }}
                  />
                  <div className="poster-overlay-btn">
                    <Play size={15} fill="currentColor" />
                  </div>
                </div>
                <div className="poster-meta">
                  <div className="poster-title" title={song.title}>
                    {song.title}
                  </div>
                  <div className="poster-subtitle">
                    {song.album || song.artist || 'Tamil Track'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 3. Featured Soundtracks */}
      {featuredMovies.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Film size={17} color="var(--accent-secondary)" />
              <h2 style={{ fontSize: '17px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Soundtracks & Albums
              </h2>
            </div>
            <button
              onClick={() => navigateTo('movies')}
              style={{ background: 'none', border: 'none', color: 'var(--accent-primary)', fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
            >
              All Soundtracks <ChevronRight size={14} />
            </button>
          </div>

          <div
            className="grid-responsive"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(190px, 1fr))',
              gap: '18px',
            }}
          >
            {featuredMovies.map((movie) => {
              const trackCount = movie.track_count || movie.total_songs || 0;
              const downloadedCount = movie.downloaded_count ?? 0;

              return (
                <div
                  key={movie.id}
                  onClick={() => navigateTo('movie_detail', movie.id)}
                  className="poster-card"
                >
                  <div className="poster-img-wrap aspect-2-3">
                    <img
                      src={api.getArtworkUrl('movie', movie.id, 400, 600)}
                      alt={movie.title}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      loading="lazy"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src =
                          'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="450" fill="%2316161a"><rect width="300" height="450"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%238B7CF8" font-size="36">🎬</text></svg>';
                      }}
                    />
                    {movie.year && (
                      <div
                        style={{
                          position: 'absolute',
                          top: '8px',
                          right: '8px',
                          backgroundColor: 'rgba(11, 11, 13, 0.85)',
                          backdropFilter: 'blur(8px)',
                          color: 'var(--text-primary)',
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 7px',
                          borderRadius: 'var(--radius-xs)',
                          border: '1px solid rgba(255, 255, 255, 0.1)',
                          fontVariantNumeric: 'tabular-nums',
                        }}
                      >
                        {movie.year}
                      </div>
                    )}
                  </div>

                  <div className="poster-meta">
                    <div className="poster-title" title={movie.title}>
                      {movie.title}
                    </div>
                    <div className="poster-subtitle">
                      {trackCount} songs {downloadedCount > 0 ? `· ${downloadedCount} ready` : ''}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* 4. Top Artists & Composers */}
      {topArtists.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Users size={17} color="#2DD4BF" />
              <h2 style={{ fontSize: '17px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Artists & Composers
              </h2>
            </div>
            <button
              onClick={() => navigateTo('artists')}
              style={{ background: 'none', border: 'none', color: 'var(--accent-primary)', fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
            >
              All Artists <ChevronRight size={14} />
            </button>
          </div>

          <div
            className="grid-responsive"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))',
              gap: '16px',
            }}
          >
            {topArtists.map((artist) => (
              <div
                key={artist.id}
                onClick={() => navigateTo('artist_detail', artist.id)}
                className="poster-card"
                style={{
                  alignItems: 'center',
                  textAlign: 'center',
                  padding: '18px 12px 14px',
                }}
              >
                <div
                  style={{
                    width: '88px',
                    height: '88px',
                    borderRadius: '50%',
                    overflow: 'hidden',
                    backgroundColor: 'var(--bg-inset)',
                    marginBottom: '10px',
                    border: '2px solid var(--border-medium)',
                  }}
                >
                  <img
                    src={api.getArtworkUrl('artist', artist.id, 200, 200)}
                    alt={artist.name}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" fill="%2316161a"><rect width="200" height="200"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23BAB0FB" font-size="28">👤</text></svg>';
                    }}
                  />
                </div>

                <div className="poster-title" title={artist.name} style={{ width: '100%' }}>
                  {artist.name}
                </div>
                <div className="poster-subtitle" style={{ width: '100%', textTransform: 'capitalize' }}>
                  {artist.role ? artist.role.replace('_', ' ') : 'Artist'}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 5. Discover & Add Tracks */}
      {missingSongs.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Download size={17} color="var(--accent-primary)" />
              <h2 style={{ fontSize: '17px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Discover & Download ({missingCount} Available)
              </h2>
            </div>
            <Button
              variant="secondary"
              onClick={handleDownloadAllMissing}
              disabled={queuingMissing}
              style={{ fontSize: '12px', padding: '6px 14px' }}
            >
              <Download size={13} /> Download All Missing
            </Button>
          </div>

          <div
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))',
              gap: '12px',
            }}
          >
            {missingSongs.map((song) => (
              <div
                key={song.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '10px 14px',
                  borderRadius: 'var(--radius-lg)',
                  backgroundColor: 'var(--bg-surface)',
                  border: '1px solid var(--border-subtle)',
                  gap: '12px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0, flex: 1 }}>
                  <img
                    src={api.getArtworkUrl('song', song.id, 96, 96)}
                    alt={song.title}
                    style={{
                      width: '44px',
                      height: '44px',
                      borderRadius: 'var(--radius-sm)',
                      objectFit: 'cover',
                      backgroundColor: '#16161a',
                      flexShrink: 0,
                    }}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" fill="%2316161a"><rect width="44" height="44"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%238B7CF8" font-size="16">🎵</text></svg>';
                    }}
                  />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: '13.5px', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {song.title}
                    </div>
                    <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: '2px' }}>
                      {song.artist || 'Unknown'} {song.album ? `• ${song.album}` : ''}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                  <QualityBadge quality={song.quality} isDownloaded={false} />
                  <button
                    onClick={() => handleDownloadSingle(song.id, song.title)}
                    className="btn-icon"
                    style={{ width: '32px', height: '32px', color: 'var(--accent-primary)', backgroundColor: 'rgba(139, 124, 248, 0.1)' }}
                    title="Download track"
                  >
                    <Download size={14} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
};
