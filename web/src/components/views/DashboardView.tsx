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
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '36px' }}>
      {/* 1. Hero / Library Identity */}
      <div
        className="glass-panel"
        style={{
          padding: '16px 24px',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '24px',
          position: 'relative',
          overflow: 'hidden',
          borderRadius: 'var(--radius-xl)',
          backgroundColor: 'transparent',
        }}
      >
        <div style={{ zIndex: 2, maxWidth: '640px' }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '6px', color: 'var(--text-secondary)', fontSize: '12px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: '8px' }}>
            <Sparkles size={14} /> Personal Music Vault
          </div>
          <h1 className="title-display" style={{ fontSize: '32px', fontWeight: 800, margin: 0, color: '#f8fafc' }}>
            Tamil MP3 Library
          </h1>
          <p style={{ color: 'var(--text-secondary)', marginTop: '8px', fontSize: '14px', lineHeight: 1.5, marginBottom: '20px' }}>
            Discover, organize and download Tamil music in high quality.
          </p>

          {/* Minimalist Stats Chips */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap', fontSize: '13px', color: 'var(--text-muted)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-success)', fontWeight: 600 }}>
              <CheckCircle2 size={15} /> {stats?.total_owned ?? 0} Downloaded
            </span>
            <span>•</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#f8fafc' }}>
              <Music size={14} color="var(--accent-primary)" /> {stats?.total_songs ?? 0} Catalog Songs
            </span>
            <span>•</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#f8fafc' }}>
              <Film size={14} color="var(--accent-secondary)" /> {stats?.total_movies ?? 0} Soundtracks
            </span>
            <span>•</span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', color: '#f8fafc' }}>
              <HardDrive size={14} color="#f59e0b" /> {formatBytes(stats?.total_storage_bytes)}
            </span>
          </div>
        </div>

        {/* Quick Hero Actions */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', zIndex: 2 }}>
          {missingCount > 0 && (
            <Button
              variant="primary"
              onClick={handleDownloadAllMissing}
              disabled={queuingMissing}
              style={{ padding: '12px 24px', gap: '8px', fontSize: '13px', fontWeight: 600 }}
            >
              <Download size={16} /> Download Missing ({missingCount})
            </Button>
          )}
          <Button
            variant="secondary"
            onClick={() => navigateTo('movies')}
            style={{ padding: '10px 20px', gap: '8px', fontSize: '13px' }}
          >
            <Film size={15} /> Browse All Soundtracks
          </Button>
        </div>
      </div>

      {/* 2. Recently Downloaded Shelf */}
      {downloadedSongs.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <CheckCircle2 size={18} color="var(--color-success)" />
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Recently Downloaded
              </h2>
            </div>
            <button
              onClick={() => navigateTo('songs')}
              style={{ background: 'none', border: 'none', color: 'var(--accent-primary)', fontSize: '13px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px', cursor: 'pointer' }}
            >
              View All Songs <ChevronRight size={14} />
            </button>
          </div>

          <div
            className="grid-responsive"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))',
              gap: '16px',
            }}
          >
            {downloadedSongs.map((song) => (
              <Card
                key={song.id}
                onClick={() => playSong(song, downloadedSongs)}
                className="glass-card"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  padding: '12px',
                  borderRadius: 'var(--radius-lg)',
                  cursor: 'pointer',
                  position: 'relative',
                }}
              >
                <div
                  style={{
                    width: '100%',
                    aspectRatio: '1',
                    borderRadius: 'var(--radius-md)',
                    overflow: 'hidden',
                    position: 'relative',
                    backgroundColor: '#1e293b',
                    marginBottom: '10px',
                  }}
                >
                  <img
                    src={api.getArtworkUrl('song', song.id, 240, 240)}
                    alt={song.title}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" fill="%231e293b"><rect width="200" height="200"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%2364748b" font-size="24">🎵</text></svg>';
                    }}
                  />
                  <div
                    style={{
                      position: 'absolute',
                      bottom: '8px',
                      right: '8px',
                      width: '32px',
                      height: '32px',
                      borderRadius: '50%',
                      backgroundColor: 'var(--accent-primary)',
                      color: '#ffffff',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      boxShadow: '0 4px 10px rgba(0,0,0,0.4)',
                    }}
                  >
                    <Play size={14} fill="currentColor" />
                  </div>
                </div>

                <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {song.title}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: '2px' }}>
                  {song.artist || song.album || 'Tamil Track'}
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* 3. Featured Soundtracks */}
      {featuredMovies.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Film size={18} color="var(--accent-secondary)" />
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Featured Soundtracks
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
              gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
              gap: '20px',
            }}
          >
            {featuredMovies.map((movie) => {
              const trackCount = movie.track_count || movie.total_songs || 0;
              const downloadedCount = movie.downloaded_count ?? 0;

              return (
                <Card
                  key={movie.id}
                  onClick={() => navigateTo('movie_detail', movie.id)}
                  className="glass-card"
                  style={{
                    display: 'flex',
                    flexDirection: 'column',
                    padding: '12px',
                    borderRadius: 'var(--radius-lg)',
                    cursor: 'pointer',
                  }}
                >
                  <div
                    style={{
                      width: '100%',
                      aspectRatio: '2 / 3',
                      borderRadius: 'var(--radius-md)',
                      overflow: 'hidden',
                      position: 'relative',
                      backgroundColor: '#0f172a',
                      marginBottom: '10px',
                    }}
                  >
                    <img
                      src={api.getArtworkUrl('movie', movie.id, 400, 600)}
                      alt={movie.title}
                      style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                      loading="lazy"
                      onError={(e) => {
                        (e.target as HTMLImageElement).src =
                          'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="450" fill="%230f172a"><rect width="300" height="450"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%236366f1" font-size="36">🎬</text></svg>';
                      }}
                    />
                    {movie.year && (
                      <div
                        style={{
                          position: 'absolute',
                          top: '8px',
                          right: '8px',
                          backgroundColor: 'rgba(15, 23, 42, 0.85)',
                          color: '#f8fafc',
                          fontSize: '11px',
                          fontWeight: 700,
                          padding: '2px 7px',
                          borderRadius: 'var(--radius-xs)',
                        }}
                      >
                        {movie.year}
                      </div>
                    )}
                  </div>

                  <div style={{ fontWeight: 700, fontSize: '14px', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {movie.title}
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '2px' }}>
                    {trackCount} songs {downloadedCount > 0 ? `· ${downloadedCount} ready` : ''}
                  </div>
                </Card>
              );
            })}
          </div>
        </section>
      )}

      {/* 4. Top Artists & Composers Row */}
      {topArtists.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Users size={18} color="#f59e0b" />
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Top Artists & Composers
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
              gridTemplateColumns: 'repeat(auto-fill, minmax(170px, 1fr))',
              gap: '16px',
            }}
          >
            {topArtists.map((artist) => (
              <Card
                key={artist.id}
                onClick={() => navigateTo('artist_detail', artist.id)}
                className="glass-card"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  textAlign: 'center',
                  padding: '20px 14px',
                  borderRadius: 'var(--radius-xl)',
                  cursor: 'pointer',
                }}
              >
                <div
                  style={{
                    width: '96px',
                    height: '96px',
                    borderRadius: '50%',
                    overflow: 'hidden',
                    backgroundColor: '#0f172a',
                    marginBottom: '12px',
                    border: '2px solid var(--border-medium)',
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)',
                  }}
                >
                  <img
                    src={api.getArtworkUrl('artist', artist.id, 200, 200)}
                    alt={artist.name}
                    style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="200" height="200" fill="%230f172a"><rect width="200" height="200"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23a5b4fc" font-size="28">👤</text></svg>';
                    }}
                  />
                </div>

                <div style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '100%' }}>
                  {artist.name}
                </div>
                <div style={{ fontSize: '11px', color: 'var(--text-secondary)', marginTop: '2px', textTransform: 'capitalize' }}>
                  {artist.role ? artist.role.replace('_', ' ') : 'Artist'}
                </div>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* 5. Missing Tracks from Library (Quick Discovery) */}
      {missingSongs.length > 0 && (
        <section style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Download size={18} color="var(--accent-primary)" />
              <h2 style={{ fontSize: '18px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                Missing in Library ({missingCount} Available)
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

          <div className="glass-panel" style={{ overflow: 'hidden', borderRadius: 'var(--radius-lg)' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '48px' }}>Art</th>
                  <th>Title</th>
                  <th>Artist</th>
                  <th>Soundtrack</th>
                  <th>Quality</th>
                  <th style={{ textAlign: 'right', width: '100px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {missingSongs.map((song) => (
                  <tr key={song.id}>
                    <td>
                      <img
                        src={api.getArtworkUrl('song', song.id, 80, 80)}
                        alt={song.title}
                        style={{ width: '36px', height: '36px', borderRadius: 'var(--radius-sm)', objectFit: 'cover', backgroundColor: '#1e293b' }}
                        loading="lazy"
                        onError={(e) => {
                          (e.target as HTMLImageElement).src =
                            'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="36" height="36" fill="%231e293b"><rect width="36" height="36"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%2364748b" font-size="12">🎵</text></svg>';
                        }}
                      />
                    </td>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{song.title}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{song.artist || '—'}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{song.album || '—'}</td>
                    <td>
                      <QualityBadge quality={song.quality} isDownloaded={false} />
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <button
                        onClick={() => handleDownloadSingle(song.id, song.title)}
                        className="btn-icon"
                        style={{ width: '32px', height: '32px', color: 'var(--accent-primary)' }}
                        title="Download track"
                      >
                        <Download size={14} />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
};
