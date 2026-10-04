import React, { useEffect, useState } from 'react';
import {
  Music,
  CheckCircle2,
  Film,
  Users,
  HardDrive,
  Play,
  Download,
  ChevronRight,
  Disc3,
  Sparkles,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { QualityBadge } from '../common/Badge';
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
  const [_loading, setLoading] = useState(true);
  const [queuingMissing, setQueuingMissing] = useState(false);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const [downloadedRes, missingRes, moviesRes, artistsRes] = await Promise.all([
          songsApi.getSongs({ state: 'OWNED', page_size: 6, sort_by: 'id', sort_order: 'desc' }),
          songsApi.getSongs({ state: 'NEW', page_size: 6, sort_by: 'id', sort_order: 'desc' }),
          moviesApi.getMovies({ page_size: 6, sort_by: 'track_count', sort_order: 'desc' }),
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

  const handlePlayMovieSoundtrack = async (movie: Movie) => {
    try {
      const res = await moviesApi.getMovieSongs(movie.id);
      if (res.success && res.data && res.data.songs && res.data.songs.length > 0) {
        const owned = res.data.songs.filter(s => s.has_file || s.file_path || s.state === 'OWNED');
        if (owned.length > 0) {
          playSong(owned[0], owned);
          showToast(`Playing soundtrack: ${movie.title}`, 'info');
        } else {
          showToast(`Download tracks first to play "${movie.title}"`, 'warning');
        }
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to play movie soundtrack', 'error');
    }
  };

  const formatBytes = (bytes?: number) => {
    if (!bytes) return '0 MB';
    const mb = bytes / (1024 * 1024);
    if (mb > 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${Math.round(mb)} MB`;
  };

  const missingCount = Math.max(0, (stats?.total_songs ?? 0) - (stats?.total_owned ?? 0));
  const spotlightMovie = featuredMovies.length > 0 ? featuredMovies[0] : null;

  return (
    <div className="view-container" style={{ gap: '32px' }}>
      {/* 1. Asymmetric Curated Hero Bento (2/3 Spotlight + 1/3 Collection Pulse) */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))',
          gap: '20px',
          alignItems: 'stretch',
        }}
      >
        {/* Left: Featured Album / Soundtrack Spotlight */}
        <div
          className="double-bezel"
          style={{
            flex: 2,
            minHeight: '260px',
            display: 'flex',
          }}
        >
          <div
            className="double-bezel-inner"
            style={{
              padding: '24px 28px',
              width: '100%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              gap: '24px',
              position: 'relative',
              overflow: 'hidden',
              background: 'linear-gradient(135deg, rgba(20, 23, 32, 0.95) 0%, rgba(14, 16, 22, 0.98) 100%)',
            }}
          >
            {/* Ambient artwork glow backdrop */}
            {spotlightMovie && (
              <div
                style={{
                  position: 'absolute',
                  right: '-10%',
                  top: '-20%',
                  width: '320px',
                  height: '320px',
                  borderRadius: '50%',
                  background: 'radial-gradient(circle, rgba(212, 163, 89, 0.14) 0%, transparent 70%)',
                  pointerEvents: 'none',
                  filter: 'blur(30px)',
                }}
              />
            )}

            <div style={{ maxWidth: '520px', zIndex: 1 }}>
              <div
                style={{
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: '6px',
                  padding: '3px 9px',
                  borderRadius: 'var(--radius-pill)',
                  backgroundColor: 'rgba(212, 163, 89, 0.12)',
                  border: '1px solid rgba(212, 163, 89, 0.28)',
                  fontSize: '11px',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: 'var(--accent-primary)',
                  marginBottom: '12px',
                }}
              >
                <Sparkles size={12} />
                <span>Soundtrack Spotlight</span>
              </div>

              <h1
                className="title-display"
                style={{
                  fontSize: '28px',
                  fontWeight: 800,
                  lineHeight: 1.15,
                  margin: 0,
                  color: 'var(--text-primary)',
                }}
              >
                {spotlightMovie ? spotlightMovie.title : 'Tamil Music Library'}
              </h1>

              <p
                style={{
                  color: 'var(--text-secondary)',
                  marginTop: '8px',
                  fontSize: '13.5px',
                  marginBottom: '20px',
                  lineHeight: 1.5,
                }}
              >
                {spotlightMovie
                  ? `${spotlightMovie.track_count || spotlightMovie.total_songs || 0} canonical audio tracks ${spotlightMovie.year ? `· Released in ${spotlightMovie.year}` : ''}. High-fidelity personal collection.`
                  : 'Personal curated collection of Tamil cinema soundtracks, classical compositions, and high-fidelity tracks.'}
              </p>

              <div style={{ display: 'flex', alignItems: 'center', gap: '12px', flexWrap: 'wrap' }}>
                {spotlightMovie && (
                  <button
                    onClick={() => handlePlayMovieSoundtrack(spotlightMovie)}
                    className="btn btn-primary"
                    style={{
                      padding: '10px 20px',
                      borderRadius: 'var(--radius-pill)',
                      fontWeight: 600,
                      fontSize: '13px',
                    }}
                  >
                    <Play size={16} fill="currentColor" /> Play Soundtrack
                  </button>
                )}
                <button
                  onClick={() => navigateTo('movies')}
                  className="btn btn-secondary"
                  style={{
                    padding: '10px 18px',
                    borderRadius: 'var(--radius-pill)',
                    fontWeight: 500,
                    fontSize: '13px',
                  }}
                >
                  <Film size={15} /> Browse Soundtracks
                </button>
              </div>
            </div>

            {/* Spotlight Movie Poster Preview */}
            {spotlightMovie && (
              <div
                onClick={() => navigateTo('movie_detail', spotlightMovie.id)}
                style={{
                  width: '135px',
                  height: '190px',
                  borderRadius: 'var(--radius-md)',
                  overflow: 'hidden',
                  flexShrink: 0,
                  cursor: 'pointer',
                  border: '1px solid var(--border-medium)',
                  boxShadow: '0 8px 24px rgba(0, 0, 0, 0.65)',
                  position: 'relative',
                  zIndex: 1,
                  display: 'none',
                }}
                className="desktop-spotlight-poster"
              >
                <img
                  src={api.getArtworkUrl('movie', spotlightMovie.id, 270, 380)}
                  alt={spotlightMovie.title}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  loading="lazy"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="270" height="380" fill="%2311141c"><rect width="270" height="380"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="32">🎬</text></svg>';
                  }}
                />
              </div>
            )}
          </div>
        </div>

        {/* Right: Integrated Collection Pulse Bento */}
        <div
          className="double-bezel"
          style={{
            flex: 1,
            minWidth: '280px',
            display: 'flex',
          }}
        >
          <div
            className="double-bezel-inner"
            style={{
              padding: '22px 24px',
              width: '100%',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '16px',
            }}
          >
            <div>
              <div
                style={{
                  fontSize: '11px',
                  fontWeight: 700,
                  letterSpacing: '0.08em',
                  textTransform: 'uppercase',
                  color: 'var(--text-muted)',
                  marginBottom: '14px',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '6px',
                }}
              >
                <Disc3 size={13} color="var(--accent-primary)" />
                <span>Collection Pulse</span>
              </div>

              {/* Hardware Metric Rows */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <CheckCircle2 size={15} color="var(--color-success)" /> Ready to Stream
                  </span>
                  <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                    {stats?.total_owned ?? 0}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Music size={15} color="var(--accent-primary)" /> Total Catalog Tracks
                  </span>
                  <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                    {stats?.total_songs ?? 0}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Film size={15} color="var(--text-muted)" /> Soundtracks
                  </span>
                  <span style={{ fontSize: '14px', fontWeight: 700, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                    {stats?.total_movies ?? 0}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ fontSize: '13px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <HardDrive size={15} color="var(--accent-primary)" /> Disk Usage
                  </span>
                  <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-secondary)', fontVariantNumeric: 'tabular-nums' }}>
                    {formatBytes(stats?.total_storage_bytes)}
                  </span>
                </div>
              </div>
            </div>

            {/* Quick Action Inside Pulse */}
            {missingCount > 0 ? (
              <button
                onClick={handleDownloadAllMissing}
                disabled={queuingMissing}
                className="btn btn-primary"
                style={{
                  width: '100%',
                  padding: '9px 14px',
                  borderRadius: 'var(--radius-md)',
                  fontSize: '12.5px',
                  fontWeight: 600,
                  gap: '8px',
                }}
              >
                <Download size={14} /> Download Missing ({missingCount})
              </button>
            ) : (
              <div
                style={{
                  padding: '8px 12px',
                  borderRadius: 'var(--radius-sm)',
                  backgroundColor: 'rgba(34, 197, 94, 0.08)',
                  border: '1px solid rgba(34, 197, 94, 0.20)',
                  fontSize: '12px',
                  color: 'var(--color-success)',
                  textAlign: 'center',
                  fontWeight: 600,
                }}
              >
                Catalog Synchronized (100% Ready)
              </div>
            )}
          </div>
        </div>
      </div>

      {/* 2. Recently Downloaded Shelf (Vinyl Record Aesthetic) */}
      {downloadedSongs.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <div
                style={{
                  width: '8px',
                  height: '8px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--color-success)',
                  boxShadow: '0 0 8px rgba(34, 197, 94, 0.4)',
                }}
              />
              <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Recently Downloaded
              </h2>
            </div>
            <button
              onClick={() => navigateTo('songs')}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--accent-primary)',
                fontSize: '12.5px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                cursor: 'pointer',
              }}
            >
              View All Tracks <ChevronRight size={14} />
            </button>
          </div>

          <div
            className="grid-responsive"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))',
              gap: '16px',
            }}
          >
            {downloadedSongs.map((song) => (
              <div
                key={song.id}
                onClick={() => playSong(song, downloadedSongs)}
                className="poster-card"
                style={{
                  backgroundColor: 'var(--bg-surface)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div className="poster-img-wrap">
                  <img
                    src={api.getArtworkUrl('song', song.id, 240, 240)}
                    alt={song.title}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" fill="%2311141c"><rect width="200" height="200"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="24">🎵</text></svg>';
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
                    {song.album && song.album !== '-' && song.album !== '—'
                      ? song.album
                      : song.artist && song.artist !== '-' && song.artist !== '—'
                      ? song.artist
                      : 'Tamil Soundtrack'}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* 3. Featured Soundtracks & Albums (2:3 Cinematic Posters) */}
      {featuredMovies.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Film size={16} color="var(--accent-primary)" />
              <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Soundtracks & Albums
              </h2>
            </div>
            <button
              onClick={() => navigateTo('movies')}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--accent-primary)',
                fontSize: '12.5px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                cursor: 'pointer',
              }}
            >
              All Soundtracks <ChevronRight size={14} />
            </button>
          </div>

          <div
            className="grid-responsive"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(185px, 1fr))',
              gap: '18px',
            }}
          >
            {featuredMovies.map((movie) => {
              const trackCount = movie.track_count || movie.total_songs || 0;
              const downloadedCount = movie.downloaded_count ?? 0;
              const isComplete = trackCount > 0 && downloadedCount >= trackCount;

              return (
                <div
                  key={movie.id}
                  onClick={() => navigateTo('movie_detail', movie.id)}
                  className="poster-card"
                  style={{
                    backgroundColor: 'var(--bg-surface)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div className="poster-img-wrap aspect-2-3">
                    <img
                      src={api.getArtworkUrl('movie', movie.id, 400, 600)}
                      alt={movie.title}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      loading="lazy"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src =
                          'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="450" fill="%2311141c"><rect width="300" height="450"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="36">🎬</text></svg>';
                      }}
                    />
                    {movie.year && (
                      <div
                        style={{
                          position: 'absolute',
                          top: '8px',
                          right: '8px',
                          backgroundColor: 'rgba(7, 8, 10, 0.85)',
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
                    {isComplete && (
                      <div
                        style={{
                          position: 'absolute',
                          bottom: '8px',
                          left: '8px',
                          backgroundColor: 'rgba(7, 8, 10, 0.85)',
                          backdropFilter: 'blur(8px)',
                          color: 'var(--color-success)',
                          fontSize: '10px',
                          fontWeight: 700,
                          padding: '2px 6px',
                          borderRadius: 'var(--radius-xs)',
                          border: '1px solid rgba(34, 197, 94, 0.3)',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '4px',
                        }}
                      >
                        <CheckCircle2 size={11} /> Ready
                      </div>
                    )}
                  </div>

                  <div className="poster-meta">
                    <div className="poster-title" title={movie.title}>
                      {movie.title}
                    </div>
                    <div className="poster-subtitle">
                      {trackCount} tracks {downloadedCount > 0 && !isComplete ? `· ${downloadedCount} ready` : ''}
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
              <Users size={16} color="var(--accent-primary)" />
              <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Artists & Composers
              </h2>
            </div>
            <button
              onClick={() => navigateTo('artists')}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--accent-primary)',
                fontSize: '12.5px',
                fontWeight: 600,
                display: 'flex',
                alignItems: 'center',
                gap: '4px',
                cursor: 'pointer',
              }}
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
                  padding: '20px 14px 16px',
                  backgroundColor: 'var(--bg-surface)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div
                  style={{
                    width: '84px',
                    height: '84px',
                    borderRadius: '50%',
                    overflow: 'hidden',
                    backgroundColor: 'var(--bg-inset)',
                    marginBottom: '12px',
                    border: '2px solid rgba(212, 163, 89, 0.25)',
                    boxShadow: '0 4px 14px rgba(0, 0, 0, 0.5)',
                  }}
                >
                  <img
                    src={api.getArtworkUrl('artist', artist.id, 200, 200)}
                    alt={artist.name}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" fill="%2311141c"><rect width="200" height="200"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="28">👤</text></svg>';
                    }}
                  />
                </div>

                <div className="poster-title" title={artist.name} style={{ width: '100%', fontSize: '13px' }}>
                  {artist.name}
                </div>
                <div
                  className="poster-subtitle"
                  style={{
                    width: '100%',
                    textTransform: 'capitalize',
                    color: 'var(--text-muted)',
                    fontSize: '11px',
                    marginTop: '2px',
                  }}
                >
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
              <Download size={16} color="var(--accent-primary)" />
              <h2 style={{ fontSize: '16px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Discover & Download ({missingCount} Available)
              </h2>
            </div>
            <button
              onClick={handleDownloadAllMissing}
              disabled={queuingMissing}
              className="btn btn-secondary"
              style={{ fontSize: '12px', padding: '6px 14px', borderRadius: 'var(--radius-pill)' }}
            >
              <Download size={13} /> Download All Missing
            </button>
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
                  borderRadius: 'var(--radius-md)',
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
                      width: '42px',
                      height: '42px',
                      borderRadius: 'var(--radius-sm)',
                      objectFit: 'cover',
                      backgroundColor: 'var(--bg-inset)',
                      flexShrink: 0,
                    }}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="42" height="42" fill="%2311141c"><rect width="42" height="42"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="16">🎵</text></svg>';
                    }}
                  />
                  <div style={{ minWidth: 0, flex: 1 }}>
                    <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {song.title}
                    </div>
                    <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: '2px' }}>
                      {song.artist || 'Unknown'} {song.album ? `· ${song.album}` : ''}
                    </div>
                  </div>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                  <QualityBadge quality={song.quality} isDownloaded={false} />
                  <button
                    onClick={() => handleDownloadSingle(song.id, song.title)}
                    className="btn-icon"
                    style={{
                      width: '32px',
                      height: '32px',
                      color: 'var(--accent-primary)',
                      backgroundColor: 'rgba(212, 163, 89, 0.12)',
                      border: '1px solid rgba(212, 163, 89, 0.28)',
                    }}
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
