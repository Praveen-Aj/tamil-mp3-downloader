import React, { useEffect, useState, useCallback } from 'react';
import { Search, Film, Download, ChevronLeft, ChevronRight, Music } from 'lucide-react';
import { moviesApi } from '../../api/endpoints';
import { Movie } from '../../api/types';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { useApp } from '../../context/AppContext';
import { api } from '../../api/client';

export const MoviesView: React.FC = () => {
  const { showToast, navigateTo, refreshStats } = useApp();
  const [movies, setMovies] = useState<Movie[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(18);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(false);

  const loadMovies = useCallback(async () => {
    setLoading(true);
    try {
      const res = await moviesApi.getMovies({
        query: query.trim(),
        page,
        page_size: pageSize,
      });

      if (res.success && res.data) {
        setMovies(res.data.items || []);
        setTotal(res.data.total || 0);
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to load movies', 'error');
    } finally {
      setLoading(false);
    }
  }, [query, page, pageSize, showToast]);

  useEffect(() => {
    loadMovies();
  }, [loadMovies]);

  const handleDownloadAll = async (e: React.MouseEvent, movieId: number, title: string) => {
    e.stopPropagation();
    try {
      const res = await moviesApi.startDownload(movieId);
      if (res.success) {
        showToast(`Queued ${res.data.queued_count} songs from "${title}"`, 'success');
        refreshStats();
        loadMovies();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to download movie songs', 'error');
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
            placeholder="Search movie soundtracks..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            style={{ flex: 1, fontSize: '13px' }}
          />
        </div>

        <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
          {total} Movies in database
        </div>
      </div>

      {/* Movies Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          Loading soundtrack albums...
        </div>
      ) : movies.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          No movies matching "{query}" found.
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(220px, 1fr))',
            gap: '20px',
          }}
        >
          {movies.map((movie) => (
            <Card
              key={movie.id}
              onClick={() => navigateTo('movie_detail', movie.id)}
              className="glass-card"
              style={{ display: 'flex', flexDirection: 'column', padding: '14px' }}
            >
              {/* Artwork Poster */}
              <div
                style={{
                  width: '100%',
                  aspectRatio: '1',
                  borderRadius: 'var(--radius-md)',
                  overflow: 'hidden',
                  position: 'relative',
                  backgroundColor: 'var(--bg-surface-active)',
                  marginBottom: '12px',
                }}
              >
                <img
                  src={api.getArtworkUrl('movie', movie.id, 240, 240)}
                  alt={movie.title || movie.name}
                  style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                  loading="lazy"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="240" height="240" fill="%231e1b4b"><rect width="240" height="240"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23fff" font-size="28">🎬</text></svg>';
                  }}
                />
              </div>

              {/* Title & Metadata */}
              <div style={{ flex: 1 }}>
                <h4
                  style={{
                    fontSize: '14px',
                    fontWeight: 700,
                    color: 'var(--text-primary)',
                    whiteSpace: 'nowrap',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                  }}
                >
                  {movie.title || movie.name}
                </h4>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {movie.year || 'Soundtrack'}
                </div>
              </div>

              {/* Stats & Download Button */}
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginTop: '12px',
                  paddingTop: '10px',
                  borderTop: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '11px', color: 'var(--text-secondary)' }}>
                  <Music size={12} />
                  <span>{movie.total_songs ?? 0} tracks</span>
                </div>

                <Button
                  size="sm"
                  variant="primary"
                  onClick={(e) => handleDownloadAll(e, movie.id, movie.title || movie.name || '')}
                  title="Download all movie tracks"
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
