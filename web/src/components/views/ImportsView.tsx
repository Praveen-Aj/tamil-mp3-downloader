import React, { useState } from 'react';
import {
  Link2,
  Search,
  CheckCircle2,
  Loader2,
  AlertCircle,
  ArrowRight,
  Download,
  CheckSquare,
  Square,
  Music,
  ExternalLink,
  Layers,
} from 'lucide-react';
import { importsApi } from '../../api/endpoints';
import { ImportJob, ImportJobItem } from '../../api/types';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { useApp } from '../../context/AppContext';

export const ImportsView: React.FC = () => {
  const { showToast, refreshStats, navigateTo } = useApp();
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [currentJob, setCurrentJob] = useState<ImportJob | null>(null);
  const [selectedItemIds, setSelectedItemIds] = useState<Set<number>>(new Set());

  const handleStartImport = async () => {
    if (!url.trim()) {
      showToast('Please enter a Spotify, YouTube, or web URL', 'warning');
      return;
    }

    setLoading(true);
    setSelectedItemIds(new Set());
    try {
      const res = await importsApi.startUrlImport(url.trim());
      if (res.success && res.data) {
        const job = res.data;
        setCurrentJob(job);
        showToast('Playlist analysis and track matching complete', 'success');
        refreshStats();

        // Auto-select matched tracks that are not already downloaded
        const initialSelected = new Set<number>();
        (job.items || []).forEach((item: ImportJobItem) => {
          if (item.is_matched && !item.is_owned) {
            initialSelected.add(item.id);
          }
        });
        setSelectedItemIds(initialSelected);
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to analyze playlist URL', 'error');
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSelect = (itemId: number) => {
    setSelectedItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  };

  const handleSelectAllMatched = () => {
    if (!currentJob || !currentJob.items) return;
    const next = new Set<number>();
    currentJob.items.forEach((item) => {
      if (item.is_matched && !item.is_owned) {
        next.add(item.id);
      }
    });
    setSelectedItemIds(next);
  };

  const handleDeselectAll = () => {
    setSelectedItemIds(new Set());
  };

  const handleDownloadSelected = async () => {
    if (!currentJob) return;
    if (selectedItemIds.size === 0) {
      showToast('Please select at least one track to download', 'warning');
      return;
    }

    setDownloading(true);
    try {
      const res = await importsApi.executeImport({
        job_id: currentJob.id,
        item_ids: Array.from(selectedItemIds),
        create_playlist: true,
      });

      if (res.success) {
        showToast(`Queued ${selectedItemIds.size} tracks for download`, 'success');
        refreshStats();
        // Clear selection
        setSelectedItemIds(new Set());
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue downloads', 'error');
    } finally {
      setDownloading(false);
    }
  };

  const handleDownloadAllMatched = async () => {
    if (!currentJob) return;

    setDownloading(true);
    try {
      const res = await importsApi.executeImport({
        job_id: currentJob.id,
        create_playlist: true,
      });

      if (res.success) {
        showToast('Queued all eligible matched tracks for download', 'success');
        refreshStats();
        setSelectedItemIds(new Set());
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue all matched downloads', 'error');
    } finally {
      setDownloading(false);
    }
  };

  const getPlatformIconColor = (platform?: string) => {
    if (platform === 'spotify') return '#1db954';
    if (platform === 'youtube') return '#ff0000';
    return 'var(--accent-primary)';
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds) return '-';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  };

  const items = currentJob?.items || [];
  const matchedItems = items.filter((it) => it.is_matched);
  const unmatchedItems = items.filter((it) => !it.is_matched);
  const unownedMatchedCount = matchedItems.filter((it) => !it.is_owned).length;

  return (
    <div className="view-container" style={{ maxWidth: '980px', margin: '0 auto', gap: '24px' }}>
      {/* 1. Header */}
      <div style={{ textAlign: 'center' }}>
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, #10b981 0%, #22C55E 100%)',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 8px 24px rgba(16, 185, 129, 0.25)',
            marginBottom: '16px',
          }}
        >
          <Link2 size={28} color="#ffffff" />
        </div>
        <h2 className="title-display" style={{ fontSize: '24px', fontWeight: 800 }}>
          Import from Spotify & Web
        </h2>
        <p style={{ color: 'var(--text-secondary)', marginTop: '8px', fontSize: '14px' }}>
          Paste a Spotify playlist, album, or track link. The engine automatically matches metadata and queries verified sources for 320 kbps downloads.
        </p>
      </div>

      {/* 2. URL Input Bar */}
      <div
        className="table-card"
        style={{
          padding: '24px',
          display: 'flex',
          flexDirection: 'column',
          gap: '16px',
        }}
      >
        <div>
          <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '8px' }}>
            Playlist or Track Link
          </label>
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-medium)',
              borderRadius: 'var(--radius-md)',
              padding: '8px 14px',
              gap: '10px',
            }}
          >
            <Link2 size={18} color="var(--text-muted)" />
            <input
              type="url"
              placeholder="https://open.spotify.com/playlist/... or https://youtube.com/watch?v=..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleStartImport();
              }}
              style={{ flex: 1, fontSize: '14px', color: 'var(--text-primary)', background: 'transparent', border: 'none', outline: 'none' }}
            />
            {url && (
              <button
                onClick={() => setUrl('')}
                style={{ background: 'none', border: 'none', color: 'var(--text-muted)', cursor: 'pointer', fontSize: '12px' }}
              >
                ✕
              </button>
            )}
          </div>
        </div>

        <Button
          variant="primary"
          onClick={handleStartImport}
          loading={loading}
          style={{ width: '100%', padding: '12px', fontSize: '14px', gap: '8px' }}
        >
          Analyze & Match Tracks <ArrowRight size={16} />
        </Button>
      </div>

      {/* 3. Job Status & Actions Display */}
      {currentJob && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
          {/* Summary Metric Cards */}
          <div className="glass-panel" style={{ padding: '24px' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <div
                  style={{
                    width: '12px',
                    height: '12px',
                    borderRadius: '50%',
                    backgroundColor: getPlatformIconColor(currentJob.platform),
                  }}
                />
                <div>
                  <span style={{ fontWeight: 700, fontSize: '16px', color: '#f8fafc' }}>
                    {currentJob.title || `${currentJob.platform.toUpperCase()} Import`}
                  </span>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {currentJob.url}
                  </div>
                </div>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                <Badge variant={currentJob.status === 'completed' ? 'success' : 'primary'}>
                  {currentJob.status}
                </Badge>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', textAlign: 'center' }}>
              <div style={{ padding: '14px', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Total Tracks</div>
                <div className="title-display" style={{ fontSize: '22px', marginTop: '4px', fontWeight: 800 }}>
                  {currentJob.total_tracks}
                </div>
              </div>
              <div style={{ padding: '14px', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Matched Sources</div>
                <div className="title-display" style={{ fontSize: '22px', marginTop: '4px', color: 'var(--accent-secondary)', fontWeight: 800 }}>
                  {currentJob.matched_tracks}
                </div>
              </div>
              <div style={{ padding: '14px', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Already in Library</div>
                <div className="title-display" style={{ fontSize: '22px', marginTop: '4px', color: 'var(--color-success)', fontWeight: 800 }}>
                  {currentJob.downloaded_tracks}
                </div>
              </div>
            </div>
          </div>

          {/* Action Toolbar */}
          <div
            className="glass-panel"
            style={{
              padding: '16px 20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              flexWrap: 'wrap',
              gap: '12px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Button size="sm" variant="ghost" onClick={handleSelectAllMatched}>
                Select All Matched
              </Button>
              <Button size="sm" variant="ghost" onClick={handleDeselectAll}>
                Deselect All
              </Button>
              <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                {selectedItemIds.size} selected
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <Button
                variant="secondary"
                onClick={handleDownloadSelected}
                disabled={selectedItemIds.size === 0 || downloading}
                loading={downloading}
                style={{ gap: '6px', fontSize: '13px' }}
              >
                <Download size={14} /> Download Selected ({selectedItemIds.size})
              </Button>

              {unownedMatchedCount > 0 && (
                <Button
                  variant="primary"
                  onClick={handleDownloadAllMatched}
                  disabled={downloading}
                  loading={downloading}
                  style={{ gap: '6px', fontSize: '13px' }}
                >
                  <Download size={14} /> Download All Matched ({unownedMatchedCount})
                </Button>
              )}
            </div>
          </div>

          {/* 4. Matched Tracks Table */}
          <div className="table-card">
            <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h3 style={{ fontSize: '15px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                  Matched Tracks ({matchedItems.length})
                </h3>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                  Verified audio sources ready for 320 kbps streaming & download
                </div>
              </div>
            </div>

            {matchedItems.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                No matching audio sources found for this URL.
              </div>
            ) : (
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '40px', textAlign: 'center' }}>
                      <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>✓</span>
                    </th>
                    <th style={{ width: '40px', textAlign: 'center' }}>#</th>
                    <th>Track Title</th>
                    <th>Artist</th>
                    <th>Source Provider</th>
                    <th style={{ width: '80px' }}>Duration</th>
                    <th style={{ width: '120px', textAlign: 'right' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {matchedItems.map((item, index) => {
                    const isSelected = selectedItemIds.has(item.id);
                    const isOwned = item.is_owned;

                    return (
                      <tr
                        key={item.id}
                        style={{
                          backgroundColor: isSelected ? 'rgba(212, 163, 89, 0.08)' : undefined,
                          opacity: isOwned ? 0.75 : 1,
                        }}
                      >
                        {/* Checkbox */}
                        <td style={{ textAlign: 'center' }}>
                          {isOwned ? (
                            <CheckCircle2 size={16} color="var(--color-success)" style={{ display: 'inline-block' }} />
                          ) : (
                            <button
                              onClick={() => handleToggleSelect(item.id)}
                              style={{
                                background: 'none',
                                border: 'none',
                                cursor: 'pointer',
                                color: isSelected ? 'var(--accent-primary)' : 'var(--text-muted)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                padding: 0,
                                margin: '0 auto',
                              }}
                              title={isSelected ? 'Deselect track' : 'Select track'}
                            >
                              {isSelected ? <CheckSquare size={16} /> : <Square size={16} />}
                            </button>
                          )}
                        </td>

                        {/* Track Number */}
                        <td style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                          {item.track_index || index + 1}
                        </td>

                        {/* Title */}
                        <td style={{ fontWeight: 600, color: '#f8fafc' }}>
                          {item.title}
                        </td>

                        {/* Artist */}
                        <td style={{ color: 'var(--text-secondary)', fontSize: '12.5px' }}>
                          {item.artist || 'Unknown Artist'}
                        </td>

                        {/* Provider */}
                        <td>
                          <span
                            style={{
                              fontSize: '11px',
                              padding: '2px 8px',
                              borderRadius: 'var(--radius-xs)',
                              backgroundColor: 'rgba(255, 255, 255, 0.06)',
                              color: 'var(--text-secondary)',
                              fontWeight: 500,
                            }}
                          >
                            {item.provider || 'Web Audio'}
                          </span>
                        </td>

                        {/* Duration */}
                        <td style={{ color: 'var(--text-muted)', fontSize: '12px', fontVariantNumeric: 'tabular-nums' }}>
                          {formatDuration(item.duration_sec)}
                        </td>

                        {/* Status */}
                        <td style={{ textAlign: 'right' }}>
                          {isOwned ? (
                            <span style={{ color: 'var(--color-success)', fontSize: '11.5px', display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 600 }}>
                              <CheckCircle2 size={13} /> In Library
                            </span>
                          ) : (
                            <span style={{ color: 'var(--accent-primary)', fontSize: '11.5px', display: 'inline-flex', alignItems: 'center', gap: '4px', fontWeight: 500 }}>
                              Ready to Download
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </div>

          {/* 5. Unmatched Tracks Table (if any) */}
          {unmatchedItems.length > 0 && (
            <div className="glass-panel" style={{ overflow: 'hidden', borderRadius: 'var(--radius-lg)' }}>
              <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', alignItems: 'center', gap: '8px' }}>
                <AlertCircle size={16} color="var(--color-warning)" />
                <div>
                  <h3 style={{ fontSize: '14px', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
                    Unmatched Tracks ({unmatchedItems.length})
                  </h3>
                  <div style={{ fontSize: '11.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    These tracks could not be automatically matched with high-fidelity streams on active audio providers.
                  </div>
                </div>
              </div>

              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '40px', textAlign: 'center' }}>#</th>
                    <th>Track Title</th>
                    <th>Artist</th>
                    <th>Album</th>
                    <th style={{ textAlign: 'right', width: '120px' }}>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {unmatchedItems.map((item, index) => (
                    <tr key={item.id} style={{ opacity: 0.6 }}>
                      <td style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                        {item.track_index || index + 1}
                      </td>
                      <td style={{ fontWeight: 500, color: 'var(--text-secondary)' }}>
                        {item.title}
                      </td>
                      <td style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                        {item.artist || '-'}
                      </td>
                      <td style={{ color: 'var(--text-muted)', fontSize: '12px' }}>
                        {item.album || '-'}
                      </td>
                      <td style={{ textAlign: 'right', color: 'var(--text-muted)', fontSize: '11.5px' }}>
                        No Match Found
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
