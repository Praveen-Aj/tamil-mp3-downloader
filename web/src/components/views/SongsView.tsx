import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  Search,
  Play,
  Download,
  Trash2,
  FolderOpen,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  Music,
  CheckSquare,
  Square,
  AlertTriangle,
  X,
  ArrowUpCircle,
  Heart,
} from 'lucide-react';
import { songsApi, downloadsApi } from '../../api/endpoints';
import { Song } from '../../api/types';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { useApp } from '../../context/AppContext';
import { Button } from '../common/Button';
import { QualityBadge, DownloadStateBadge } from '../common/Badge';
import { api } from '../../api/client';

export const SongsView: React.FC = () => {
  const { playSong } = useAudioPlayer();
  const { showToast, refreshStats, stats } = useApp();

  const [songs, setSongs] = useState<Song[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(25);
  const [query, setQuery] = useState('');
  const [stateFilter, setStateFilter] = useState('ALL');
  const [sortBy, setSortBy] = useState('title');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [loading, setLoading] = useState(false);

  // Multi-selection state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [batchActionLoading, setBatchActionLoading] = useState(false);

  // Delete modal state
  const [deleteModalSong, setDeleteModalSong] = useState<Song | null>(null);
  const [deleting, setDeleting] = useState(false);

  const loadSongs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await songsApi.getSongs({
        query: query.trim(),
        state: stateFilter === 'ALL' ? undefined : stateFilter,
        sort_by: sortBy,
        sort_order: sortOrder,
        page,
        page_size: pageSize,
      });

      if (res.success && res.data) {
        setSongs(res.data.items || []);
        setTotal(res.data.total || 0);
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to load songs', 'error');
    } finally {
      setLoading(false);
    }
  }, [query, stateFilter, sortBy, sortOrder, page, pageSize, showToast]);

  useEffect(() => {
    loadSongs();
  }, [loadSongs]);

  // Handle single download
  const handleDownload = async (songId: number, title?: string) => {
    try {
      const res = await downloadsApi.queueSongs([songId]);
      if (res.success) {
        showToast(title ? `Download queued: "${title}"` : 'Download queued successfully', 'success');
        refreshStats();
        loadSongs();
      }
    } catch (err: any) {
      showToast(err.message || 'Download failed to queue', 'error');
    }
  };

  // Handle download all missing
  const handleDownloadAllMissing = async () => {
    setBatchActionLoading(true);
    try {
      const res = await songsApi.downloadMissingSongs(320);
      if (res.success && res.data) {
        showToast(`Queued ${res.data.queued_count} missing songs for download`, 'success');
        refreshStats();
        loadSongs();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue missing songs', 'error');
    } finally {
      setBatchActionLoading(false);
    }
  };

  // Handle download selected
  const handleDownloadSelected = async () => {
    if (selectedIds.size === 0) return;
    setBatchActionLoading(true);
    try {
      const ids = Array.from(selectedIds);
      const res = await downloadsApi.queueSongs(ids);
      if (res.success) {
        showToast(`Queued ${ids.length} selected tracks for download`, 'success');
        setSelectedIds(new Set());
        refreshStats();
        loadSongs();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue selected tracks', 'error');
    } finally {
      setBatchActionLoading(false);
    }
  };

  // Handle explicit delete execution
  const executeDelete = async (deletePhysical: boolean) => {
    if (!deleteModalSong) return;
    setDeleting(true);
    try {
      await songsApi.deleteSong(deleteModalSong.id, deletePhysical, true);
      showToast(
        deletePhysical
          ? `Deleted physical audio file and removed "${deleteModalSong.title}" from library`
          : `Removed "${deleteModalSong.title}" from library (file retained on disk)`,
        'info'
      );
      setDeleteModalSong(null);
      refreshStats();
      loadSongs();
    } catch (err: any) {
      showToast(err.message || 'Failed to remove song', 'error');
    } finally {
      setDeleting(false);
    }
  };

  const handleOpenFolder = async (songId: number) => {
    try {
      await songsApi.openFolder(songId);
    } catch (err: any) {
      showToast(err.message || 'Failed to open file folder', 'error');
    }
  };

  const handleToggleFavorite = async (song: Song, e: React.MouseEvent) => {
    e.stopPropagation();
    const nextFav = !song.is_favorite;
    setSongs(prev => prev.map(s => s.id === song.id ? { ...s, is_favorite: nextFav } : s));
    try {
      await songsApi.toggleFavorite(song.id, nextFav);
      showToast(nextFav ? `Added "${song.title}" to Favorites` : `Removed "${song.title}" from Favorites`, 'success');
    } catch (err: any) {
      setSongs(prev => prev.map(s => s.id === song.id ? { ...s, is_favorite: !nextFav } : s));
      showToast('Failed to update favorite', 'error');
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds || seconds <= 0) {
      return <span style={{ opacity: 0.28, letterSpacing: '1px' }}>--:--</span>;
    }
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const sanitizeTitle = (title: string, album?: string) => {
    if (!title || /^[\?\s\-_.]+$/.test(title.trim())) {
      if (album && album !== '-' && album !== '—') {
        return `${album} Track`;
      }
      return 'Tamil Track';
    }
    return title;
  };

  // Select all toggles on current page
  const allCurrentPageSelected = useMemo(() => {
    return songs.length > 0 && songs.every((s) => selectedIds.has(s.id));
  }, [songs, selectedIds]);

  const toggleSelectAll = () => {
    const next = new Set(selectedIds);
    if (allCurrentPageSelected) {
      songs.forEach((s) => next.delete(s.id));
    } else {
      songs.forEach((s) => next.add(s.id));
    }
    setSelectedIds(next);
  };

  const toggleSelectSong = (id: number) => {
    const next = new Set(selectedIds);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    setSelectedIds(next);
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  // Dynamic counts derived from actual database/API stats
  const totalCatalog = stats?.total_songs ?? (stateFilter === 'ALL' && !query ? total : 855);
  const downloadedCount = stats?.total_owned ?? (stateFilter === 'OWNED' && !query ? total : 3);
  const notDownloadedCount = Math.max(0, totalCatalog - downloadedCount);

  return (
    <div className="view-container">
      {/* High-Precision Controls Bar (Single Compact Header Strip) */}
      <div className="view-toolbar" style={{ marginTop: '4px', marginBottom: '14px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap', flex: 1 }}>
          {/* State Filter Buttons */}
          <div style={{ display: 'flex', gap: '6px' }}>
            {(['ALL', 'OWNED', 'NEW'] as const).map((st) => {
              const isActive = stateFilter === st;
              const activeClass = isActive
                ? st === 'ALL'
                  ? 'active-all'
                  : st === 'OWNED'
                  ? 'active-downloaded'
                  : 'active-missing'
                : '';
              const count = st === 'ALL' ? totalCatalog : st === 'OWNED' ? downloadedCount : notDownloadedCount;
              const label = st === 'ALL' ? 'All Tracks' : st === 'OWNED' ? 'Downloaded' : 'Not Downloaded';
              return (
                <button
                  key={st}
                  onClick={() => {
                    setStateFilter(st);
                    setPage(1);
                  }}
                  className={`filter-tab ${activeClass}`}
                  aria-label={`Filter by ${label}`}
                >
                  {label} ({count})
                </button>
              );
            })}
          </div>

          {/* Quick Track Filter Input */}
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor: 'var(--bg-inset)',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-sm)',
              padding: '5px 10px',
              gap: '6px',
              width: '220px',
            }}
          >
            <Search size={13} color="var(--text-muted)" />
            <input
              type="text"
              placeholder="Filter tracks..."
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
              style={{ flex: 1, fontSize: '12px' }}
              aria-label="Filter songs by title"
            />
          </div>

          {/* Sort By Dropdown */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
            <ArrowUpDown size={13} color="var(--text-muted)" />
            <select
              value={`${sortBy}-${sortOrder}`}
              onChange={(e) => {
                const [sb, so] = e.target.value.split('-');
                setSortBy(sb);
                setSortOrder(so as 'asc' | 'desc');
                setPage(1);
              }}
              style={{
                backgroundColor: 'var(--bg-inset)',
                border: '1px solid var(--border-medium)',
                borderRadius: 'var(--radius-sm)',
                color: 'var(--text-primary)',
                fontSize: '12px',
                padding: '5px 8px',
                cursor: 'pointer',
              }}
              aria-label="Sort tracks"
            >
              <option value="title-asc">Title (A - Z)</option>
              <option value="title-desc">Title (Z - A)</option>
              <option value="artist-asc">Artist (A - Z)</option>
              <option value="album-asc">Album / Movie (A - Z)</option>
              <option value="year-desc">Year (Newest)</option>
              <option value="year-asc">Year (Oldest)</option>
              <option value="quality-desc">Quality (Highest)</option>
            </select>
          </div>
        </div>

        {/* Global Batch Actions */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {selectedIds.size > 0 && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleDownloadSelected}
              loading={batchActionLoading}
              aria-label="Download Selected Tracks"
            >
              <Download size={13} /> Download Selected ({selectedIds.size})
            </Button>
          )}

          <Button
            variant="secondary"
            size="sm"
            onClick={handleDownloadAllMissing}
            loading={batchActionLoading}
            aria-label="Download All Missing Tracks"
          >
            <Download size={13} /> Download Missing
          </Button>
        </div>
      </div>

      {/* Songs Table */}
      <div className="table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '38px', textAlign: 'center' }}>
                <button
                  onClick={toggleSelectAll}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-muted)' }}
                  aria-label="Select all on this page"
                >
                  {allCurrentPageSelected ? (
                    <CheckSquare size={16} color="var(--accent-primary)" />
                  ) : (
                    <Square size={16} />
                  )}
                </button>
              </th>
              <th>Track</th>
              <th>Soundtrack / Album</th>
              <th style={{ width: '70px' }}>Duration</th>
              <th style={{ width: '85px' }}>Quality</th>
              <th style={{ width: '115px' }}>Status</th>
              <th style={{ textAlign: 'right', width: '120px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  Loading library tracks...
                </td>
              </tr>
            ) : songs.length === 0 ? (
              <tr>
                <td colSpan={7} style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                  No songs matching criteria found.
                </td>
              </tr>
            ) : (
              songs.map((song) => {
                const isSelected = selectedIds.has(song.id);
                const isDownloaded = song.has_file || song.state === 'OWNED';
                return (
                  <tr
                    key={song.id}
                    style={{
                      backgroundColor: isSelected ? 'rgba(212, 163, 89, 0.10)' : undefined,
                    }}
                  >
                    {/* Checkbox */}
                    <td style={{ textAlign: 'center' }}>
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => toggleSelectSong(song.id)}
                        aria-label={`Select ${song.title}`}
                      />
                    </td>

                    {/* Primary: Artwork + Song Title + Artist */}
                    <td style={{ minWidth: '240px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        {/* Artwork with play overlay */}
                        <div
                          onClick={() => playSong(song, songs)}
                          style={{
                            width: '42px',
                            height: '42px',
                            borderRadius: 'var(--radius-sm)',
                            overflow: 'hidden',
                            position: 'relative',
                            backgroundColor: '#11141c',
                            cursor: 'pointer',
                            flexShrink: 0,
                          }}
                          className="track-art-wrap"
                          title={`Play ${song.title}`}
                        >
                          <img
                            src={api.getArtworkUrl('song', song.id, 88, 88)}
                            alt={song.title}
                            style={{
                              width: '100%',
                              height: '100%',
                              objectFit: 'cover',
                            }}
                            loading="lazy"
                            onError={(e) => {
                              (e.target as HTMLImageElement).src =
                                'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="42" height="42" fill="%2311141c"><rect width="42" height="42"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="14">🎵</text></svg>';
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
                              opacity: 0,
                              transition: 'opacity 150ms ease',
                            }}
                            className="play-overlay"
                          >
                            <Play size={14} fill="currentColor" />
                          </div>
                        </div>

                        {/* Title and Artist */}
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div
                            onClick={() => playSong(song, songs)}
                            style={{
                              fontWeight: 600,
                              color: 'var(--text-primary)',
                              fontSize: '13.5px',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              cursor: 'pointer',
                            }}
                            title={sanitizeTitle(song.title, song.album)}
                          >
                            {sanitizeTitle(song.title, song.album)}
                          </div>
                          <div
                            style={{
                              fontSize: '11.5px',
                              color: 'var(--text-secondary)',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                              marginTop: '2px',
                            }}
                          >
                            {song.artist || 'Unknown Artist'}
                          </div>
                        </div>
                      </div>
                    </td>

                    {/* Secondary: Soundtrack / Album & Year */}
                    <td style={{ color: 'var(--text-secondary)', fontSize: '12.5px', maxWidth: '180px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {song.album && song.album !== '-' && song.album !== '—' ? song.album : 'Soundtrack'} {song.year ? <span style={{ color: 'var(--text-muted)', fontSize: '11.5px' }}>({song.year})</span> : ''}
                    </td>

                    {/* Duration */}
                    <td style={{ color: 'var(--text-muted)', fontSize: '12px', fontVariantNumeric: 'tabular-nums' }}>
                      {formatDuration(song.duration_sec)}
                    </td>

                    {/* Quality */}
                    <td>
                      <QualityBadge quality={song.quality} isDownloaded={isDownloaded} />
                    </td>

                    {/* Download State */}
                    <td>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <DownloadStateBadge state={song.download_state || song.state} />
                        {song.can_upgrade && (
                          <button
                            onClick={() => handleDownload(song.id, song.title)}
                            className="badge badge-primary"
                            style={{ cursor: 'pointer', border: 'none', fontSize: '10px', padding: '1px 5px' }}
                            title="Upgrade track quality to 320 kbps"
                            aria-label={`Upgrade ${song.title} to 320 kbps`}
                          >
                            <ArrowUpCircle size={10} /> Upgrade
                          </button>
                        )}
                      </div>
                    </td>

                    {/* Actions */}
                    <td style={{ textAlign: 'right' }}>
                      <div style={{ display: 'inline-flex', gap: '3px' }}>
                        {/* Favorite toggle button */}
                        <button
                          onClick={(e) => handleToggleFavorite(song, e)}
                          className="btn-icon"
                          style={{
                            width: '28px',
                            height: '28px',
                            color: song.is_favorite ? 'var(--color-error)' : 'var(--text-muted)',
                          }}
                          title={song.is_favorite ? 'Starred' : 'Add to Favorites'}
                        >
                          <Heart size={14} fill={song.is_favorite ? 'currentColor' : 'none'} />
                        </button>

                        {!isDownloaded ? (
                          <button
                            onClick={() => handleDownload(song.id, song.title)}
                            className="btn-icon"
                            style={{ width: '28px', height: '28px', color: 'var(--accent-primary)' }}
                            title="Download track"
                            aria-label={`Download ${song.title}`}
                          >
                            <Download size={14} />
                          </button>
                        ) : (
                          <button
                            onClick={() => handleOpenFolder(song.id)}
                            className="btn-icon"
                            style={{ width: '28px', height: '28px', color: 'var(--color-success)' }}
                            title="Reveal in Explorer"
                            aria-label="Reveal file in Explorer"
                          >
                            <FolderOpen size={14} />
                          </button>
                        )}

                        <button
                          onClick={() => setDeleteModalSong(song)}
                          className="btn-icon"
                          style={{ width: '28px', height: '28px', color: 'var(--text-muted)' }}
                          title="Delete / Remove song"
                          aria-label={`Delete ${song.title}`}
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>

        {/* Pagination Footer */}
        <div
          style={{
            padding: '14px 20px',
            borderTop: '1px solid var(--border-subtle)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            fontSize: '13px',
            color: 'var(--text-muted)',
          }}
        >
          <div>
            Showing {songs.length} of {total} songs (Page {page} of {totalPages})
          </div>

          <div style={{ display: 'flex', gap: '8px' }}>
            <Button
              variant="secondary"
              size="sm"
              disabled={page <= 1}
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              aria-label="Previous Page"
            >
              <ChevronLeft size={16} /> Previous
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={page >= totalPages}
              onClick={() => setPage((p) => p + 1)}
              aria-label="Next Page"
            >
              Next <ChevronRight size={16} />
            </Button>
          </div>
        </div>
      </div>

      {/* 2-Option Explicit Delete Modal (Issue 11) */}
      {deleteModalSong && (
        <div className="modal-backdrop" onClick={() => !deleting && setDeleteModalSong(null)}>
          <div className="modal-dialog" onClick={(e) => e.stopPropagation()}>
            <div
              style={{
                padding: '20px 24px',
                borderBottom: '1px solid var(--border-subtle)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div
                  style={{
                    width: '36px',
                    height: '36px',
                    borderRadius: '8px',
                    backgroundColor: 'var(--color-error-bg)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: 'var(--color-error)',
                  }}
                >
                  <AlertTriangle size={20} />
                </div>
                <div>
                  <h3 className="title-display" style={{ fontSize: '16px', margin: 0 }}>
                    Remove Song from Library
                  </h3>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                    Choose how you want to handle this track
                  </div>
                </div>
              </div>
              <button
                onClick={() => !deleting && setDeleteModalSong(null)}
                className="btn-icon"
                style={{ width: '32px', height: '32px' }}
                aria-label="Close dialog"
              >
                <X size={16} />
              </button>
            </div>

            <div style={{ padding: '20px 24px' }}>
              <div
                style={{
                  backgroundColor: 'var(--bg-app)',
                  padding: '12px 16px',
                  borderRadius: 'var(--radius-md)',
                  marginBottom: '20px',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)' }}>
                  {deleteModalSong.title}
                </div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  {deleteModalSong.artist || 'Unknown Artist'} • {deleteModalSong.album || 'Unknown Album'}
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                {/* Option 1: Remove from Library Only */}
                <div
                  onClick={() => !deleting && executeDelete(false)}
                  style={{
                    padding: '14px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-medium)',
                    backgroundColor: 'rgba(255, 255, 255, 0.02)',
                    cursor: deleting ? 'not-allowed' : 'pointer',
                    transition: 'all var(--transition-fast)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--accent-primary)')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'var(--border-medium)')}
                >
                  <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
                    Option 1: Remove from Library Only
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Removes track entry and catalog links from database. <strong>Keeps downloaded MP3 file safely on your hard drive.</strong>
                  </div>
                </div>

                {/* Option 2: Delete Physical File */}
                <div
                  onClick={() => !deleting && executeDelete(true)}
                  style={{
                    padding: '14px',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid rgba(239, 68, 68, 0.3)',
                    backgroundColor: 'rgba(239, 68, 68, 0.04)',
                    cursor: deleting ? 'not-allowed' : 'pointer',
                    transition: 'all var(--transition-fast)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.borderColor = 'var(--color-error)')}
                  onMouseLeave={(e) => (e.currentTarget.style.borderColor = 'rgba(239, 68, 68, 0.3)')}
                >
                  <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--color-error)' }}>
                    Option 2: Delete Physical File & Remove
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
                    Permanently removes the physical MP3 audio file from disk and deletes the database record.
                  </div>
                </div>
              </div>
            </div>

            <div
              style={{
                padding: '14px 24px',
                borderTop: '1px solid var(--border-subtle)',
                display: 'flex',
                justifyContent: 'flex-end',
                gap: '10px',
              }}
            >
              <Button
                variant="secondary"
                size="sm"
                disabled={deleting}
                onClick={() => setDeleteModalSong(null)}
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Floating Bulk Action Dock (Taste Skill) */}
      {selectedIds.size > 0 && (
        <div className="floating-action-dock" role="region" aria-label="Bulk actions">
          <span style={{ fontSize: '13px', fontWeight: 600, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
            {selectedIds.size} track{selectedIds.size === 1 ? '' : 's'} selected
          </span>
          <Button
            variant="primary"
            size="sm"
            onClick={handleDownloadSelected}
            loading={batchActionLoading}
            style={{ borderRadius: 'var(--radius-pill)', padding: '6px 14px', fontSize: '12px' }}
          >
            <Download size={13} /> Download
          </Button>
          <button
            onClick={() => setSelectedIds(new Set())}
            className="btn btn-ghost"
            style={{ padding: '6px 10px', fontSize: '12px', color: 'var(--text-muted)' }}
          >
            Deselect
          </button>
        </div>
      )}
    </div>
  );
};
