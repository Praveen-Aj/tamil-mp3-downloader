import React, { useEffect, useState, useCallback } from 'react';
import { Search, Users, Download, ChevronLeft, ChevronRight, Music } from 'lucide-react';
import { artistsApi } from '../../api/endpoints';
import { Artist } from '../../api/types';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { useApp } from '../../context/AppContext';
import { api } from '../../api/client';

export const ArtistsView: React.FC = () => {
  const { showToast, navigateTo, refreshStats } = useApp();
  const [artists, setArtists] = useState<Artist[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(18);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);

  const loadArtists = useCallback(async () => {
    setLoading(true);
    try {
      const res = await artistsApi.getArtists({
        query: query.trim(),
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
  }, [query, page, pageSize, showToast]);

  useEffect(() => {
    loadArtists();
  }, [loadArtists]);

  const handleDownloadAll = async (e: React.MouseEvent, artistId: number, name: string) => {
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

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      {/* Search Header */}
      <div
        className="glass-panel"
        style={{
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-medium)',
            borderRadius: 'var(--radius-md)',
            padding: '6px 12px',
            gap: '8px',
            width: '320px',
          }}
        >
          <Search size={15} color="var(--text-muted)" />
          <input
            type="text"
            placeholder="Search artists & composers..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            style={{ flex: 1, fontSize: '13px' }}
          />
        </div>

        <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
          {total} Artists in catalog
        </div>
      </div>

      {/* Artists Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          Loading artists...
        </div>
      ) : artists.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          No artists matching "{query}" found.
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: '20px',
          }}
        >
          {artists.map((artist) => (
            <Card
              key={artist.id}
              onClick={() => navigateTo('artist_detail', artist.id)}
              className="glass-card"
              style={{
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                textAlign: 'center',
                padding: '20px 16px',
              }}
            >
              {/* Circular Avatar */}
              <div
                style={{
                  width: '100px',
                  height: '100px',
                  borderRadius: '50%',
                  overflow: 'hidden',
                  backgroundColor: 'var(--bg-surface-active)',
                  boxShadow: 'var(--shadow-md)',
                  marginBottom: '14px',
                  border: '2px solid var(--border-medium)',
                }}
              >
                <img
                  src={api.getArtworkUrl('artist', artist.id, 120, 120)}
                  alt={artist.name}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  loading="lazy"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" fill="%230f172a"><rect width="120" height="120"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23fff" font-size="28">👤</text></svg>';
                  }}
                />
              </div>

              {/* Name & Role */}
              <h4
                style={{
                  fontSize: '14px',
                  fontWeight: 700,
                  color: 'var(--text-primary)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  width: '100%',
                }}
              >
                {artist.name}
              </h4>
              <Badge variant="subtle" style={{ marginTop: '6px' }}>
                {artist.role || 'Artist'}
              </Badge>

              {/* Stats & Action */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  width: '100%',
                  marginTop: '16px',
                  paddingTop: '12px',
                  borderTop: '1px solid var(--border-subtle)',
                }}
              >
                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                  {artist.total_tracks ?? 0} tracks
                </span>

                <Button
                  size="sm"
                  variant="primary"
                  onClick={(e) => handleDownloadAll(e, artist.id, artist.name)}
                  title="Download all artist songs"
                >
                  <Download size={13} /> Download
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          gap: '12px',
          marginTop: '12px',
        }}
      >
        <Button
          variant="secondary"
          size="sm"
          disabled={page <= 1}
          onClick={() => setPage((p) => Math.max(1, p - 1))}
        >
          <ChevronLeft size={16} /> Previous
        </Button>
        <span style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
          Page {page} of {totalPages}
        </span>
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
  );
};
