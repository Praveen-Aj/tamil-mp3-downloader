import React, { useEffect, useState, useCallback } from 'react';
import { Search, Film, Download, ChevronLeft, ChevronRight, CheckCircle2, Play } from 'lucide-react';
import { moviesApi } from '../../api/endpoints';
import { Movie } from '../../api/types';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { useApp } from '../../context/AppContext';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { api } from '../../api/client';

export const MoviesView: React.FC = () => {
  const { showToast, navigateTo, refreshStats } = useApp();
  const { playSong } = useAudioPlayer();
  const [movies, setMovies] = useState<Movie[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(18);
  const [query, setQuery] = useState('');
  const [sortBy, setSortBy] = useState<'title' | 'year' | 'track_count'>('year');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [loading, setLoading] = useState(false);
  const [hoveredMovieId, setHoveredMovieId] = useState<number | null>(null);

  const loadMovies = useCallback(async () => {
    setLoading(true);
    try {
      const res = await moviesApi.getMovies({
        query: query.trim(),
        page,
        page_size: pageSize,
        sort_by: sortBy,
        sort_order: sortOrder,
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
  }, [query, page, pageSize, sortBy, sortOrder, showToast]);

  useEffect(() => {
    loadMovies();
  }, [loadMovies]);

  const handleDownloadMissing = async (e: React.MouseEvent, movieId: number, title: string) => {
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

  const handlePlayMovie = async (e: React.MouseEvent, movieId: number) => {
    e.stopPropagation();
    try {
      const res = await moviesApi.getMovieSongs(movieId);
      if (res.success && res.data && res.data.songs && res.data.songs.length > 0) {
        const owned = res.data.songs.filter(s => s.has_file || s.file_path || s.state === 'OWNED');
        if (owned.length > 0) {
          playSong(owned[0], owned);
          showToast(`Playing soundtrack: ${res.data.movie.title}`, 'info');
        } else {
          showToast(`Download tracks first to play "${res.data.movie.title}"`, 'warning');
        }
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to play movie soundtrack', 'error');
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="view-container">
      {/* View Header */}
      <div className="view-header">
        <div className="view-header-title">
          <div className="view-header-icon" style={{ backgroundColor: 'rgba(251, 191, 36, 0.12)', borderColor: 'rgba(251, 191, 36, 0.25)', color: '#FBBF24' }}>
            <Film size={18} />
          </div>
          <div>
            <h1 className="view-title">
              Soundtracks & Albums
            </h1>
            <div className="view-subtitle">
              {total} Tamil film soundtracks
            </div>
          </div>
        </div>
      </div>

      {/* 1. Header & Controls */}
      <div className="view-toolbar">
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px', flexWrap: 'wrap', flex: 1 }}>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-md)',
              padding: '7px 14px',
              gap: '10px',
              width: '320px',
              maxWidth: '100%',
            }}
          >
            <Search size={15} color="var(--text-muted)" />
            <input
              type="text"
              placeholder="Search movies & soundtracks..."
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

          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '12px', color: 'var(--text-muted)', fontWeight: 500 }}>Sort by:</span>
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value as any);
                setPage(1);
              }}
              style={{
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                color: 'var(--text-primary)',
                borderRadius: 'var(--radius-sm)',
                padding: '6px 12px',
                fontSize: '12px',
                cursor: 'pointer',
              }}
            >
              <option value="title">Title (A-Z)</option>
              <option value="year">Release Year</option>
              <option value="track_count">Track Count</option>
            </select>
            <button
              onClick={() => setSortOrder(prev => prev === 'asc' ? 'desc' : 'asc')}
              className="btn-icon"
              style={{ width: '32px', height: '32px', borderRadius: 'var(--radius-sm)' }}
              title={`Sort ${sortOrder === 'asc' ? 'Ascending' : 'Descending'}`}
            >
              {sortOrder === 'asc' ? '↑' : '↓'}
            </button>
          </div>
        </div>

        <div style={{ fontSize: '13px', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Film size={16} color="var(--accent-secondary)" />
          <span style={{ fontWeight: 600, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>{total}</span> Soundtracks
        </div>
      </div>

      {/* 2. Movies Grid with Authentic 2:3 Vertical Posters */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '80px 20px', color: 'var(--text-muted)' }}>
          <div style={{ fontSize: '15px', fontWeight: 500, marginBottom: '8px' }}>Loading soundtrack collection...</div>
          <div style={{ fontSize: '12px' }}>Reading canonical library records & artwork</div>
        </div>
      ) : movies.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '80px 20px', color: 'var(--text-muted)' }}>
          <Film size={36} color="var(--border-medium)" style={{ marginBottom: '12px' }} />
          <div style={{ fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>No movies found</div>
          <div style={{ fontSize: '13px', marginTop: '6px' }}>Try adjusting your search query "{query}"</div>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))',
            gap: '24px',
          }}
        >
          {movies.map((movie) => {
            const trackCount = movie.track_count || movie.total_songs || 0;
            const downloadedCount = movie.downloaded_count ?? 0;
            const missingCount = Math.max(0, trackCount - downloadedCount);
            const isComplete = trackCount > 0 && downloadedCount >= trackCount;
            const isHovered = hoveredMovieId === movie.id;
            const percentDownloaded = trackCount > 0 ? (downloadedCount / trackCount) * 100 : 0;

            return (
              <Card
                key={movie.id}
                onClick={() => navigateTo('movie_detail', movie.id)}
                onMouseEnter={() => setHoveredMovieId(movie.id)}
                onMouseLeave={() => setHoveredMovieId(null)}
                className="glass-card"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  padding: '12px',
                  borderRadius: 'var(--radius-lg)',
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
                {/* 2:3 Vertical Movie Poster */}
                <div
                  style={{
                    width: '100%',
                    aspectRatio: '2 / 3',
                    borderRadius: 'var(--radius-md)',
                    overflow: 'hidden',
                    position: 'relative',
                    backgroundColor: '#0f172a',
                    marginBottom: '12px',
                    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.35)',
                  }}
                >
                  <img
                    src={api.getArtworkUrl('movie', movie.id, 400, 600)}
                    alt={movie.title || movie.name}
                    style={{
                      width: '100%',
                      height: '100%',
                      objectFit: 'cover',
                      transform: isHovered ? 'scale(1.04)' : 'scale(1)',
                      transition: 'transform 300ms ease',
                    }}
                    loading="lazy"
                    onError={(e) => {
                      (e.target as HTMLImageElement).src =
                        'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="300" height="450" fill="%2311141C"><rect width="300" height="450"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="36">🎬</text></svg>';
                    }}
                  />

                  {/* Year Tag on top-right */}
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
                        padding: '3px 8px',
                        borderRadius: 'var(--radius-xs)',
                        border: '1px solid rgba(255, 255, 255, 0.15)',
                        letterSpacing: '0.03em',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {movie.year}
                    </div>
                  )}

                  {/* Download Status Badge on top-left */}
                  {isComplete ? (
                    <div
                      style={{
                        position: 'absolute',
                        top: '8px',
                        left: '8px',
                        backgroundColor: 'rgba(34, 197, 94, 0.9)',
                        color: '#ffffff',
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '3px 7px',
                        borderRadius: 'var(--radius-xs)',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '3px',
                        textTransform: 'uppercase',
                        letterSpacing: '0.04em',
                      }}
                    >
                      <CheckCircle2 size={11} /> Ready
                    </div>
                  ) : downloadedCount > 0 ? (
                    <div
                      style={{
                        position: 'absolute',
                        top: '8px',
                        left: '8px',
                        backgroundColor: 'rgba(212, 163, 89, 0.90)',
                        color: '#060608',
                        fontSize: '10px',
                        fontWeight: 700,
                        padding: '3px 7px',
                        borderRadius: 'var(--radius-xs)',
                        textTransform: 'uppercase',
                        fontVariantNumeric: 'tabular-nums',
                      }}
                    >
                      {downloadedCount}/{trackCount}
                    </div>
                  ) : null}

                  {/* Hover Overlay with Quick Actions */}
                  {isHovered && (
                    <div
                      style={{
                        position: 'absolute',
                        inset: 0,
                        backgroundColor: 'rgba(7, 8, 10, 0.65)',
                        backdropFilter: 'blur(3px)',
                        display: 'flex',
                        flexDirection: 'column',
                        justifyContent: 'center',
                        alignItems: 'center',
                        gap: '10px',
                        padding: '16px',
                        animation: 'fadeIn 150ms ease-out',
                      }}
                    >
                      {downloadedCount > 0 && (
                        <button
                          onClick={(e) => handlePlayMovie(e, movie.id)}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            backgroundColor: 'var(--accent-primary)',
                            color: '#060608',
                            border: 'none',
                            borderRadius: 'var(--radius-pill)',
                            padding: '8px 16px',
                            fontSize: '12px',
                            fontWeight: 700,
                            cursor: 'pointer',
                            boxShadow: '0 4px 12px rgba(212, 163, 89, 0.3)',
                          }}
                        >
                          <Play size={13} fill="currentColor" /> Play Soundtrack
                        </button>
                      )}

                      {missingCount > 0 && (
                        <button
                          onClick={(e) => handleDownloadMissing(e, movie.id, movie.title || movie.name || 'Movie')}
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '6px',
                            backgroundColor: 'rgba(255, 255, 255, 0.15)',
                            color: '#ffffff',
                            border: '1px solid rgba(255, 255, 255, 0.3)',
                            backdropFilter: 'blur(6px)',
                            borderRadius: 'var(--radius-pill)',
                            padding: '7px 14px',
                            fontSize: '11px',
                            fontWeight: 600,
                            cursor: 'pointer',
                          }}
                        >
                          <Download size={13} /> Download Missing ({missingCount})
                        </button>
                      )}
                    </div>
                  )}

                  {/* Bottom Download Progress Bar on poster */}
                  {trackCount > 0 && (
                    <div
                      style={{
                        position: 'absolute',
                        bottom: 0,
                        left: 0,
                        right: 0,
                        height: '4px',
                        backgroundColor: 'rgba(0, 0, 0, 0.6)',
                      }}
                    >
                      <div
                        style={{
                          height: '100%',
                          width: `${percentDownloaded}%`,
                          backgroundColor: isComplete ? 'var(--color-success)' : 'var(--accent-primary)',
                          transition: 'width 300ms ease',
                        }}
                      />
                    </div>
                  )}
                </div>

                {/* Metadata & Actions */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <h4
                    style={{
                      fontSize: '14px',
                      fontWeight: 700,
                      color: 'var(--text-primary)',
                      whiteSpace: 'nowrap',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      marginBottom: '4px',
                    }}
                    title={movie.title || movie.name}
                  >
                    {movie.title || movie.name}
                  </h4>

                  <div
                    style={{
                      fontSize: '12px',
                      color: 'var(--text-secondary)',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '10px',
                    }}
                  >
                    <span>{movie.year || 'Soundtrack'}</span>
                    <span style={{ color: 'var(--text-muted)' }}>
                      {trackCount} {trackCount === 1 ? 'song' : 'songs'}
                      {downloadedCount > 0 ? ` · ${downloadedCount} downloaded` : ''}
                    </span>
                  </div>

                  {/* Primary Download / Detail Action */}
                  <div style={{ marginTop: 'auto' }}>
                    {missingCount > 0 ? (
                      <Button
                        variant="secondary"
                        onClick={(e) => handleDownloadMissing(e, movie.id, movie.title || movie.name || 'Movie')}
                        style={{
                          width: '100%',
                          fontSize: '11px',
                          padding: '6px 10px',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '6px',
                        }}
                      >
                        <Download size={13} color="var(--accent-primary)" />
                        Download Missing ({missingCount})
                      </Button>
                    ) : (
                      <div
                        style={{
                          fontSize: '11px',
                          color: 'var(--color-success)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '4px',
                          padding: '6px 0',
                          fontWeight: 600,
                        }}
                      >
                        <CheckCircle2 size={13} /> Complete ({downloadedCount} tracks)
                      </div>
                    )}
                  </div>
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
            Page <span style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{page}</span> of {totalPages} ({total} movies)
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
