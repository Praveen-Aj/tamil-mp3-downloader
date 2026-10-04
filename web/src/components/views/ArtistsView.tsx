import React, { useEffect, useState, useCallback } from 'react';
import { Search, Users, Download, ChevronLeft, ChevronRight, Music, Play, CheckCircle2, Sparkles } from 'lucide-react';
import { artistsApi } from '../../api/endpoints';
import { Artist } from '../../api/types';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { useApp } from '../../context/AppContext';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { api } from '../../api/client';

export const ArtistsView: React.FC = () => {
  const { showToast, navigateTo, refreshStats } = useApp();
  const { playSong } = useAudioPlayer();
  const [artists, setArtists] = useState<Artist[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(18);
  const [query, setQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState<'all' | 'music_director' | 'singer' | 'lyricist'>('all');
  const [loading, setLoading] = useState(false);
  const [hoveredArtistId, setHoveredArtistId] = useState<number | null>(null);

  const loadArtists = useCallback(async () => {
    setLoading(true);
    try {
      const res = await artistsApi.getArtists({
        query: query.trim(),
        role: roleFilter === 'all' ? undefined : roleFilter,
        page,
        page_size: pageSize,
      });

      if (res.success && res.data) {
        setArtists(res.data.items || []);
        setTotal(res.data.total || 0);
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to load artists', 'error');
    } finally {
      setLoading(false);
    }
  }, [query, roleFilter, page, pageSize, showToast]);

  useEffect(() => {
    loadArtists();
  }, [loadArtists]);

  const handleDownloadMissing = async (e: React.MouseEvent, artistId: number, name: string) => {
    e.stopPropagation();
    try {
      const res = await artistsApi.startDownload(artistId);
      if (res.success) {
        showToast(`Queued ${res.data.queued_count} songs by "${name}"`, 'success');
        refreshStats();
        loadArtists();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to download artist songs', 'error');
    }
  };

  const handlePlayArtist = async (e: React.MouseEvent, artistId: number, name: string) => {
    e.stopPropagation();
    try {
      const res = await artistsApi.getArtistSongs(artistId);
      if (res.success && res.data && res.data.songs && res.data.songs.length > 0) {
        const owned = res.data.songs.filter(s => s.has_file || s.file_path || s.state === 'OWNED');
        if (owned.length > 0) {
          playSong(owned[0], owned);
          showToast(`Playing songs by ${name}`, 'info');
        } else {
          showToast(`Download tracks first to play songs by "${name}"`, 'warning');
        }
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to play artist tracks', 'error');
    }
  };

  const formatRoleName = (role?: string) => {
    if (!role) return 'Artist';
    switch (role.toLowerCase()) {
      case 'music_director':
      case 'composer':
        return 'Music Director';
      case 'singer':
        return 'Singer';
      case 'lyricist':
        return 'Lyricist';
      default:
        return 'Artist';
    }
  };

  const getRoleBadgeColor = (role?: string) => {
    switch (role?.toLowerCase()) {
      case 'music_director':
      case 'composer':
        return { bg: 'rgba(229, 149, 0, 0.12)', text: '#FCD34D', border: 'rgba(229, 149, 0, 0.22)' };
      case 'singer':
        return { bg: 'rgba(34, 197, 94, 0.12)', text: '#86EFAC', border: 'rgba(34, 197, 94, 0.22)' };
      case 'lyricist':
        return { bg: 'rgba(229, 149, 0, 0.12)', text: '#fcd34d', border: 'rgba(229, 149, 0, 0.25)' };
      default:
        return { bg: 'rgba(148, 163, 184, 0.12)', text: '#cbd5e1', border: 'rgba(148, 163, 184, 0.25)' };
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="view-container">
      {/* View Header */}
      <div className="view-header">
        <div className="view-header-title">
          <div className="view-header-icon" style={{ backgroundColor: 'rgba(45, 212, 191, 0.12)', borderColor: 'rgba(45, 212, 191, 0.25)', color: '#2DD4BF' }}>
            <Users size={18} />
          </div>
          <div>
            <h1 className="view-title">
              Artists & Composers
            </h1>
            <div className="view-subtitle">
              {total} Tamil composers, playback singers, and lyricists
            </div>
          </div>
        </div>
      </div>

      {/* 1. Filter Tabs & Search Header */}
      <div className="view-toolbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px', flexWrap: 'wrap', flex: 1 }}>
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
              maxWidth: '100%',
            }}
          >
            <Search size={15} color="var(--text-muted)" />
            <input
              type="text"
              placeholder="Search singers, composers..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              style={{ flex: 1, fontSize: '13px', background: 'transparent', border: 'none', color: 'var(--text-primary)', outline: 'none' }}
            />
            {query && (
              <button
                onClick={() => setQuery('')}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '12px' }}
              >
                ✕
              </button>
            )}
          </div>

          {/* Role Filter Tabs */}
          <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
            {[
              { id: 'all', label: 'All Artists' },
              { id: 'music_director', label: 'Composers' },
              { id: 'singer', label: 'Singers' },
              { id: 'lyricist', label: 'Lyricists' },
            ].map((tab) => {
              const active = roleFilter === tab.id;
              return (
                <button
                  key={tab.id}
                  onClick={() => {
                    setRoleFilter(tab.id as any);
                    setPage(1);
                  }}
                  className={`filter-tab ${active ? 'active-all' : ''}`}
                >
                  {tab.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 2. Artists Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '80px 20px', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '15px', fontWeight: 500, marginBottom: '8px' }}>Loading artist catalog...</div>
          <div style={{ fontSize: '12px' }}>Connecting canonical discographies & portraits</div>
        </div>
      ) : artists.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '80px 20px', color: 'var(--text-muted)' }}>
          <Users size={36} color="var(--border-medium)" style={{ marginBottom: '12px' }} />
          <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>No artists found</div>
          <div style={{ fontSize: '13px', marginTop: '6px' }}>Try adjusting your search query or role filter</div>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: '24px',
          }}
        >
          {artists.map((artist) => {
            const trackCount = artist.total_tracks || artist.total_songs || 0;
            const downloadedCount = artist.downloaded_tracks || artist.downloaded_songs || 0;
            const missingCount = Math.max(0, trackCount - downloadedCount);
            const isComplete = trackCount > 0 && downloadedCount >= trackCount;
            const isHovered = hoveredArtistId === artist.id;
            const roleStyle = getRoleBadgeColor(artist.role);

            return (
              <Card
                key={artist.id}
                onClick={() => navigateTo('artist_detail', artist.id)}
                onMouseEnter={() => setHoveredArtistId(artist.id)}
                onMouseLeave={() => setHoveredArtistId(null)}
                className="glass-card"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  textAlign: 'center',
                  padding: '24px 16px',
                  borderRadius: 'var(--radius-xl)',
                  cursor: 'pointer',
                  position: 'relative',
                  overflow: 'hidden',
                  background: isHovered ? 'var(--bg-surface-hover)' : 'var(--bg-surface)',
                  borderColor: isHovered ? 'var(--accent-primary)' : 'var(--border-subtle)',
                  transform: isHovered ? 'translateY(-4px)' : 'none',
                  boxShadow: isHovered ? '0 12px 28px rgba(0, 0, 0, 0.5)' : 'var(--shadow-sm)',
                  transition: 'all 200ms ease',
                }}
              >
                {/* Circular Portrait with Ambient Glow */}
                <div
                  style={{
                    width: '120px',
                    height: '120px',
                    borderRadius: '50%',
                    overflow: 'hidden',
                    backgroundColor: '#0f172a',
                    marginBottom: '16px',
                    position: 'relative',
                    border: `3px solid ${isHovered ? 'var(--accent-primary)' : 'var(--border-medium)'}`,
                    boxShadow: isHovered ? '0 0 16px rgba(229, 149, 0, 0.20)' : '0 4px 12px rgba(0, 0, 0, 0.4)',
                    transition: 'all 250ms ease',
                  }}
                >
                  <img
                    src={api.getArtworkUrl('artist', artist.id, 240, 240)}
                    alt={artist.name}
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                      transform: isHovered ? 'scale(1.06)' : 'scale(1)',
                      transition: 'transform 300ms ease',
                    }}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" fill="%2311141C"><rect width="240" height="240"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23E59500" font-size="32">👤</text></svg>';
                    }}
                  />
                </div>

                {/* Name */}
                <h4
                  style={{
                    fontSize: '15px',
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                    marginBottom: '6px',
                    maxWidth: '100%',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                  title={artist.name}
                >
                  {artist.name}
                </h4>

                {/* Role Pill Badge */}
                <div
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '4px',
                    padding: '3px 10px',
                    borderRadius: 'var(--radius-pill)',
                    fontSize: '11px',
                    fontWeight: 600,
                    textTransform: 'uppercase',
                    letterSpacing: '0.04em',
                    backgroundColor: roleStyle.bg,
                    color: roleStyle.text,
                    border: `1px solid ${roleStyle.border}`,
                    marginBottom: '10px',
                  }}
                >
                  {formatRoleName(artist.role)}
                </div>

                {/* Track Stats */}
                <div style={{ fontSize: '12px', color: 'var(--text-secondary)', marginBottom: '14px' }}>
                  <span>{trackCount} {trackCount === 1 ? 'song' : 'songs'}</span>
                  {downloadedCount > 0 && (
                    <span style={{ color: 'var(--color-success)', fontWeight: 600 }}> · {downloadedCount} ready</span>
                  )}
                </div>

                {/* Quick Actions */}
                <div style={{ width: '100%', marginTop: 'auto', display: 'flex', gap: '6px' }}>
                  {downloadedCount > 0 && (
                    <Button
                      variant="ghost"
                      onClick={(e) => handlePlayArtist(e, artist.id, artist.name)}
                      style={{
                        flex: 1,
                        fontSize: '11px',
                        padding: '6px 8px',
                        gap: '4px',
                      }}
                      title={`Play tracks by ${artist.name}`}
                    >
                      <Play size={12} fill="currentColor" /> Play
                    </Button>
                  )}

                  {missingCount > 0 ? (
                    <Button
                      variant="secondary"
                      onClick={(e) => handleDownloadMissing(e, artist.id, artist.name)}
                      style={{
                        flex: 1,
                        fontSize: '11px',
                        padding: '6px 8px',
                        gap: '4px',
                      }}
                      title={`Download ${missingCount} missing tracks`}
                    >
                      <Download size={12} color="var(--accent-primary)" /> Download ({missingCount})
                    </Button>
                  ) : (
                    <div
                      style={{
                        flex: 1,
                        fontSize: '11px',
                        color: 'var(--color-success)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        gap: '4px',
                        fontWeight: 600,
                      }}
                    >
                      <CheckCircle2 size={12} /> Complete
                    </div>
                  )}
                </div>
              </Card>
            );
          })}
        </div>
      )}

      {/* 3. Pagination Controls */}
      {totalPages > 1 && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            padding: '16px 20px',
            backgroundColor: 'var(--bg-surface)',
            borderRadius: 'var(--radius-md)',
            border: '1px solid var(--border-subtle)',
            marginTop: '8px',
          }}
        >
          <div style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>
            Page <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{page}</span> of {totalPages} ({total} artists)
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <Button
              variant="secondary"
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              style={{ fontSize: '12px', padding: '6px 12px' }}
            >
              <ChevronLeft size={14} /> Previous
            </Button>
            <Button
              variant="secondary"
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              style={{ fontSize: '12px', padding: '6px 12px' }}
            >
              Next <ChevronRight size={14} />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
