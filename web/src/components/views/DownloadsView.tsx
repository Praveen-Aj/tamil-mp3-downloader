import React, { useEffect, useState, useCallback } from 'react';
import {
  ArrowDownCircle,
  CheckCircle2,
  AlertCircle,
  XCircle,
  RotateCcw,
  Clock,
  Zap,
  ChevronDown,
  ChevronUp,
  Layers,
  Music2,
} from 'lucide-react';
import { downloadsApi } from '../../api/endpoints';
import { DownloadTask, BatchJob } from '../../api/types';
import { Button } from '../common/Button';
import { QualityBadge } from '../common/Badge';
import { api } from '../../api/client';
import { useApp } from '../../context/AppContext';
import { useWebSocket } from '../../context/WebSocketContext';

export const DownloadsView: React.FC = () => {
  const { showToast, refreshStats } = useApp();
  const { subscribe } = useWebSocket();

  const [active, setActive] = useState<DownloadTask[]>([]);
  const [queue, setQueue] = useState<DownloadTask[]>([]);
  const [history, setHistory] = useState<DownloadTask[]>([]);
  const [batches, setBatches] = useState<BatchJob[]>([]);
  const [expandedBatches, setExpandedBatches] = useState<Record<string, boolean>>({});

  const loadDownloads = useCallback(async () => {
    try {
      const [res, batchRes] = await Promise.allSettled([
        downloadsApi.getDownloads(),
        downloadsApi.getBatches(),
      ]);

      if (res.status === 'fulfilled' && res.value.success && res.value.data) {
        if (Array.isArray(res.value.data)) {
          const act = res.value.data.filter((d: any) =>
            ['downloading', 'in_progress', 'DOWNLOADING', 'IN_PROGRESS'].includes(d.status)
          );
          const q = res.value.data.filter((d: any) =>
            ['pending', 'queued', 'planned', 'QUEUED', 'PLANNED'].includes(d.status)
          );
          const hist = res.value.data.filter((d: any) =>
            ['completed', 'failed', 'cancelled', 'canceled', 'COMPLETED', 'FAILED', 'CANCELLED'].includes(d.status)
          );
          setActive(act);
          setQueue(q);
          setHistory(hist);
        } else {
          setActive(res.value.data.active || []);
          setQueue(res.value.data.queue || []);
          setHistory(res.value.data.history || []);
        }
      }

      if (batchRes.status === 'fulfilled' && batchRes.value.success && batchRes.value.data) {
        setBatches(batchRes.value.data);
      }
    } catch (err: any) {
      console.error('Failed to load downloads:', err);
    }
  }, []);

  useEffect(() => {
    loadDownloads();
    const interval = setInterval(loadDownloads, 2500);
    return () => clearInterval(interval);
  }, [loadDownloads]);

  // Real-time WebSocket event listener
  useEffect(() => {
    const unsub = subscribe('*', (event) => {
      const evType = (event.type || event.event || '').toLowerCase();
      if (
        evType === 'batch.progress' ||
        evType === 'batch_progress' ||
        evType === 'download_progress' ||
        evType === 'download.progress' ||
        evType === 'download_completed' ||
        evType === 'download.completed' ||
        evType === 'download_failed' ||
        evType === 'download.failed' ||
        evType === 'queue_updated' ||
        evType === 'queue.updated'
      ) {
        if (evType === 'batch.progress' && event.data && event.data.batch_id) {
          setBatches((prev) => {
            const idx = prev.findIndex((b) => b.batch_id === event.data.batch_id);
            if (idx >= 0) {
              const updated = [...prev];
              updated[idx] = { ...updated[idx], ...event.data };
              return updated;
            }
            return [event.data, ...prev];
          });
        }
        loadDownloads();
        refreshStats();
      }
    });
    return unsub;
  }, [subscribe, loadDownloads, refreshStats]);

  const toggleBatchExpand = (batchId: string) => {
    setExpandedBatches((prev) => ({
      ...prev,
      [batchId]: !prev[batchId],
    }));
  };

  const handleCancelTrack = async (taskId: number) => {
    try {
      await downloadsApi.cancelTask(taskId);
      showToast('Track download cancelled', 'info');
      loadDownloads();
      refreshStats();
    } catch (err: any) {
      showToast(err.message || 'Failed to cancel track', 'error');
    }
  };

  const handleCancelBatch = async (batchId: string) => {
    try {
      await downloadsApi.cancelBatch(batchId);
      showToast('Batch download cancelled', 'info');
      loadDownloads();
      refreshStats();
    } catch (err: any) {
      showToast(err.message || 'Failed to cancel batch', 'error');
    }
  };

  const handleRetry = async (taskId: number) => {
    try {
      await downloadsApi.retryTask(taskId);
      showToast('Download retried', 'success');
      loadDownloads();
      refreshStats();
    } catch (err: any) {
      showToast(err.message || 'Failed to retry download', 'error');
    }
  };

  // Determine which active downloads are standalone (not part of an active multi-track batch)
  const activeBatchDownloadIds = new Set<number>();
  batches
    .filter((b) => b.status === 'in_progress' || b.status === 'pending')
    .forEach((b) => {
      if (b.tracks) {
        b.tracks.forEach((t) => activeBatchDownloadIds.add(t.download_id));
      }
    });

  const standaloneActive = active.filter((t) => !activeBatchDownloadIds.has(t.id));

  return (
    <div className="view-container" style={{ gap: '20px' }}>
      {/* 1. Header */}
      <div className="view-header">
        <div className="view-header-title">
          <div
            className="view-header-icon"
            style={{
              backgroundColor: 'rgba(16, 185, 129, 0.12)',
              borderColor: 'rgba(16, 185, 129, 0.22)',
              color: '#10B981',
            }}
          >
            <ArrowDownCircle size={20} />
          </div>
          <div>
            <h1 className="view-title">
              Downloads
            </h1>
            <div className="view-subtitle">
              {active.length > 0
                ? `${active.length} active download${active.length > 1 ? 's' : ''}${queue.length > 0 ? ` · ${queue.length} in queue` : ''}`
                : queue.length > 0
                ? `${queue.length} track${queue.length > 1 ? 's' : ''} in queue`
                : 'No active downloads in queue'}
            </div>
          </div>
        </div>
      </div>

      {/* 2. Real Batch Download Jobs Section */}
      {batches.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <h2
            className="title-display"
            style={{
              fontSize: '13px',
              margin: '0 0 2px 0',
              color: 'var(--text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: '0.06em',
              fontWeight: 700,
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <Layers size={14} color="var(--accent-primary)" />
            Batch Downloads
          </h2>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {batches.map((batch) => {
              const isExpanded = !!expandedBatches[batch.batch_id];
              const isBatchActive = batch.status === 'in_progress' || batch.status === 'pending';
              const isCancelled = batch.status === 'cancelled';
              const isCompleted = batch.status === 'completed';

              return (
                <div
                  key={batch.batch_id}
                  className="glass-panel"
                  style={{
                    padding: '16px 20px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '12px',
                    border: `1px solid ${isBatchActive ? 'rgba(212, 163, 89, 0.35)' : 'var(--border-subtle)'}`,
                    borderRadius: 'var(--radius-lg)',
                    backgroundColor: 'var(--bg-surface)',
                    boxShadow: isBatchActive ? '0 4px 20px -2px rgba(212, 163, 89, 0.08)' : 'none',
                  }}
                >
                  {/* Top row: Title, Progress count, and Action buttons */}
                  <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '16px' }}>
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <div
                          style={{
                            fontWeight: 700,
                            fontSize: '15px',
                            color: 'var(--text-primary)',
                            whiteSpace: 'nowrap',
                            overflow: 'hidden',
                            textOverflow: 'ellipsis',
                          }}
                          title={batch.title}
                        >
                          {batch.title}
                        </div>
                        {isBatchActive && (
                          <span
                            style={{
                              fontSize: '10.5px',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                              padding: '2px 8px',
                              borderRadius: 'var(--radius-pill)',
                              backgroundColor: 'rgba(212, 163, 89, 0.15)',
                              color: 'var(--accent-primary)',
                              border: '1px solid rgba(212, 163, 89, 0.3)',
                            }}
                          >
                            Active Batch
                          </span>
                        )}
                        {isCompleted && (
                          <span
                            style={{
                              fontSize: '10.5px',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                              padding: '2px 8px',
                              borderRadius: 'var(--radius-pill)',
                              backgroundColor: 'rgba(16, 185, 129, 0.15)',
                              color: '#10B981',
                              border: '1px solid rgba(16, 185, 129, 0.3)',
                            }}
                          >
                            Completed
                          </span>
                        )}
                        {isCancelled && (
                          <span
                            style={{
                              fontSize: '10.5px',
                              fontWeight: 700,
                              textTransform: 'uppercase',
                              padding: '2px 8px',
                              borderRadius: 'var(--radius-pill)',
                              backgroundColor: 'rgba(239, 68, 68, 0.15)',
                              color: '#EF4444',
                              border: '1px solid rgba(239, 68, 68, 0.3)',
                            }}
                          >
                            Cancelled
                          </span>
                        )}
                      </div>

                      {/* Summary line: 11 / 51 completed */}
                      <div
                        style={{
                          fontSize: '13px',
                          fontWeight: 600,
                          color: '#e2e8f0',
                          marginTop: '4px',
                        }}
                      >
                        {batch.completed} / {batch.total_tracks} completed
                      </div>

                      {/* Detailed breakdown: 1 downloading · 39 queued · 1 failed */}
                      <div
                        style={{
                          fontSize: '12px',
                          color: 'var(--text-secondary)',
                          marginTop: '2px',
                          display: 'flex',
                          alignItems: 'center',
                          gap: '6px',
                        }}
                      >
                        <span>{batch.active} downloading</span>
                        <span>·</span>
                        <span>{batch.queued} queued</span>
                        {batch.failed > 0 && (
                          <>
                            <span>·</span>
                            <span style={{ color: '#EF4444' }}>{batch.failed} failed</span>
                          </>
                        )}
                        {batch.cancelled > 0 && (
                          <>
                            <span>·</span>
                            <span style={{ color: 'var(--text-muted)' }}>{batch.cancelled} cancelled</span>
                          </>
                        )}
                      </div>
                    </div>

                    {/* Actions: Cancel Batch & Expand Tracks */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                      {isBatchActive && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => handleCancelBatch(batch.batch_id)}
                          style={{
                            padding: '6px 12px',
                            fontSize: '12px',
                            fontWeight: 600,
                            borderColor: 'rgba(239, 68, 68, 0.4)',
                            color: '#EF4444',
                            backgroundColor: 'rgba(239, 68, 68, 0.08)',
                          }}
                        >
                          <XCircle size={14} style={{ marginRight: '5px' }} /> Cancel Batch
                        </Button>
                      )}

                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleBatchExpand(batch.batch_id)}
                        style={{ padding: '6px 10px', fontSize: '12px', color: 'var(--text-secondary)' }}
                      >
                        {isExpanded ? (
                          <>
                            <ChevronUp size={14} style={{ marginRight: '4px' }} /> Hide Tracks
                          </>
                        ) : (
                          <>
                            <ChevronDown size={14} style={{ marginRight: '4px' }} /> Show Tracks (
                            {batch.tracks?.length || batch.total_tracks})
                          </>
                        )}
                      </Button>
                    </div>
                  </div>

                  {/* Batch Progress Bar */}
                  <div
                    style={{
                      height: '6px',
                      backgroundColor: 'rgba(255, 255, 255, 0.08)',
                      borderRadius: 'var(--radius-pill)',
                      overflow: 'hidden',
                    }}
                  >
                    <div
                      style={{
                        height: '100%',
                        width: `${batch.overall_percentage || 0}%`,
                        backgroundColor: isCancelled ? '#EF4444' : 'var(--accent-primary)',
                        transition: 'width 250ms ease',
                      }}
                    />
                  </div>

                  {/* Currently Downloading track indication */}
                  {batch.current_track && isBatchActive && (
                    <div
                      style={{
                        fontSize: '12px',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '6px',
                        color: 'var(--accent-primary)',
                        backgroundColor: 'rgba(212, 163, 89, 0.08)',
                        padding: '6px 10px',
                        borderRadius: 'var(--radius-md)',
                        border: '1px solid rgba(212, 163, 89, 0.18)',
                      }}
                    >
                      <Zap size={13} />
                      <span style={{ fontWeight: 600 }}>Currently downloading:</span>
                      <span style={{ color: '#f8fafc', fontWeight: 500 }}>{batch.current_track}</span>
                    </div>
                  )}

                  {/* Expandable Child Tracks Accordion */}
                  {isExpanded && batch.tracks && batch.tracks.length > 0 && (
                    <div
                      style={{
                        marginTop: '4px',
                        display: 'flex',
                        flexDirection: 'column',
                        gap: '6px',
                        maxHeight: '340px',
                        overflowY: 'auto',
                        paddingRight: '4px',
                        borderTop: '1px solid var(--border-subtle)',
                        paddingTop: '10px',
                      }}
                    >
                      {batch.tracks.map((track, trackIdx) => {
                        const trkStatus = (track.status || '').toLowerCase();
                        const isDownloading = trkStatus === 'downloading' || trkStatus === 'in_progress' || track.is_active;
                        const isQueued = trkStatus === 'pending' || trkStatus === 'queued' || trkStatus === 'planned';
                        const isCompleted = trkStatus === 'completed';
                        const isFailed = trkStatus === 'failed';
                        const isTrackCancelled = trkStatus === 'cancelled' || trkStatus === 'canceled';

                        return (
                          <div
                            key={track.download_id || trackIdx}
                            style={{
                              display: 'flex',
                              alignItems: 'center',
                              justifyContent: 'space-between',
                              padding: '8px 12px',
                              backgroundColor: isDownloading
                                ? 'rgba(212, 163, 89, 0.1)'
                                : 'rgba(255, 255, 255, 0.02)',
                              borderRadius: 'var(--radius-md)',
                              border: isDownloading
                                ? '1px solid rgba(212, 163, 89, 0.28)'
                                : '1px solid rgba(255, 255, 255, 0.04)',
                            }}
                          >
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0, flex: 1 }}>
                              <div
                                style={{
                                  fontSize: '11px',
                                  color: 'var(--text-muted)',
                                  width: '20px',
                                  fontVariantNumeric: 'tabular-nums',
                                }}
                              >
                                {trackIdx + 1}.
                              </div>
                              <Music2
                                size={14}
                                color={isDownloading ? 'var(--accent-primary)' : 'var(--text-muted)'}
                              />
                              <div style={{ minWidth: 0, flex: 1 }}>
                                <div
                                  style={{
                                    fontSize: '13px',
                                    fontWeight: 500,
                                    color: isDownloading ? '#f8fafc' : '#cbd5e1',
                                    whiteSpace: 'nowrap',
                                    overflow: 'hidden',
                                    textOverflow: 'ellipsis',
                                  }}
                                  title={track.title}
                                >
                                  {track.title}
                                </div>
                                {track.artist && (
                                  <div
                                    style={{
                                      fontSize: '11px',
                                      color: 'var(--text-muted)',
                                      whiteSpace: 'nowrap',
                                      overflow: 'hidden',
                                      textOverflow: 'ellipsis',
                                    }}
                                  >
                                    {track.artist}
                                  </div>
                                )}
                              </div>
                            </div>

                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexShrink: 0 }}>
                              {isDownloading && (
                                <span
                                  style={{
                                    fontSize: '11px',
                                    color: 'var(--accent-primary)',
                                    fontWeight: 600,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '4px',
                                  }}
                                >
                                  <Zap size={11} /> Downloading
                                </span>
                              )}
                              {isQueued && (
                                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Queued</span>
                              )}
                              {isCompleted && (
                                <span
                                  style={{
                                    fontSize: '11px',
                                    color: '#10B981',
                                    fontWeight: 600,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '4px',
                                  }}
                                >
                                  <CheckCircle2 size={12} /> Downloaded
                                </span>
                              )}
                              {isFailed && (
                                <span
                                  style={{
                                    fontSize: '11px',
                                    color: '#EF4444',
                                    fontWeight: 600,
                                    display: 'flex',
                                    alignItems: 'center',
                                    gap: '4px',
                                  }}
                                >
                                  <AlertCircle size={12} /> Failed
                                </span>
                              )}
                              {isTrackCancelled && (
                                <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Cancelled</span>
                              )}

                              {/* Individual Cancel Track action for active/queued track */}
                              {(isDownloading || isQueued) && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleCancelTrack(track.download_id)}
                                  title="Cancel only this track"
                                  style={{ padding: '4px 8px', fontSize: '11px', color: 'var(--color-error)' }}
                                >
                                  <XCircle size={13} style={{ marginRight: '3px' }} /> Cancel Track
                                </Button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 3. Standalone Active Downloads (Non-batch or independent singles) */}
      <div>
        <h2
          className="title-display"
          style={{
            fontSize: '13px',
            marginBottom: '8px',
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            fontWeight: 700,
          }}
        >
          {batches.length > 0 ? 'Individual Active Downloads' : 'Active Downloads'}
        </h2>
        {standaloneActive.length === 0 ? (
          batches.length === 0 ? (
            <div
              className="glass-panel"
              style={{
                padding: '16px 20px',
                textAlign: 'center',
                color: 'var(--text-muted)',
                fontSize: '13px',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-subtle)',
                borderRadius: 'var(--radius-lg)',
              }}
            >
              Queue is empty. Select tracks or albums to download high-fidelity MP3s.
            </div>
          ) : null
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {standaloneActive.map((task) => (
              <div
                key={task.id}
                className="glass-panel"
                style={{
                  padding: '14px 18px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-lg)',
                  backgroundColor: 'var(--bg-surface)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '14px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0, flex: 1 }}>
                    <img
                      src={api.getArtworkUrl('song', task.song_id, 80, 80)}
                      alt={task.title}
                      style={{
                        width: '42px',
                        height: '42px',
                        borderRadius: 'var(--radius-sm)',
                        objectFit: 'cover',
                        backgroundColor: '#16161a',
                        flexShrink: 0,
                      }}
                      onError={(e) => {
                        (e.target as HTMLImageElement).src =
                          'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="42" height="42" fill="%2316161a"><rect width="42" height="42"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="16">🎵</text></svg>';
                      }}
                    />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div
                        style={{
                          fontWeight: 600,
                          fontSize: '14px',
                          color: '#f8fafc',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                        }}
                      >
                        {task.title}
                      </div>
                      <div
                        style={{
                          fontSize: '12px',
                          color: 'var(--text-secondary)',
                          whiteSpace: 'nowrap',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          marginTop: '2px',
                        }}
                      >
                        {task.artist || 'Tamil Track'} {task.album ? `· ${task.album}` : ''}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                    <QualityBadge quality={task.quality} />
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleCancelTrack(task.id)}
                      aria-label="Cancel download"
                      style={{ padding: '6px 10px', fontSize: '12px' }}
                    >
                      <XCircle size={14} color="var(--color-error)" /> Cancel
                    </Button>
                  </div>
                </div>

                {/* Progress Bar */}
                <div
                  style={{
                    height: '5px',
                    backgroundColor: 'rgba(255, 255, 255, 0.08)',
                    borderRadius: 'var(--radius-pill)',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${task.progress || 0}%`,
                      backgroundColor: 'var(--accent-primary)',
                      transition: 'width 200ms ease',
                    }}
                  />
                </div>

                {/* Speed & ETA */}
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    fontSize: '11.5px',
                    color: 'var(--text-muted)',
                  }}
                >
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Zap size={12} color="var(--accent-primary)" /> {task.speed_str || 'Connecting...'}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={12} /> {task.eta_str || 'Calculating...'}
                    </span>
                  </div>
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)', fontVariantNumeric: 'tabular-nums' }}>
                    {Math.round(task.progress || 0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 4. Recently Downloaded History */}
      <div>
        <h2
          className="title-display"
          style={{
            fontSize: '13px',
            marginBottom: '8px',
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            fontWeight: 700,
          }}
        >
          Download History
        </h2>
        {history.length === 0 ? (
          <div
            className="glass-panel"
            style={{
              padding: '32px',
              textAlign: 'center',
              color: 'var(--text-muted)',
              fontSize: '13.5px',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              borderRadius: 'var(--radius-lg)',
            }}
          >
            No download history recorded.
          </div>
        ) : (
          <div className="glass-panel" style={{ overflow: 'hidden', borderRadius: 'var(--radius-lg)' }}>
            <table className="data-table" style={{ width: '100%', tableLayout: 'fixed' }}>
              <thead>
                <tr>
                  <th style={{ width: '125px' }}>Status</th>
                  <th>Track</th>
                  <th style={{ width: '240px' }}>Soundtrack / Album</th>
                  <th style={{ width: '140px' }}>Quality</th>
                  <th style={{ textAlign: 'right', width: '105px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 20).map((task) => (
                  <tr key={task.id}>
                    <td style={{ width: '125px', whiteSpace: 'nowrap' }}>
                      {task.status === 'completed' ? (
                        <div
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '5px',
                            color: 'var(--color-success)',
                            fontSize: '12px',
                            fontWeight: 600,
                          }}
                        >
                          <CheckCircle2 size={14} /> Downloaded
                        </div>
                      ) : (
                        <div
                          style={{
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '5px',
                            color: 'var(--color-error)',
                            fontSize: '12px',
                            fontWeight: 600,
                          }}
                        >
                          <AlertCircle size={14} /> Failed
                        </div>
                      )}
                    </td>
                    <td style={{ minWidth: 0, overflow: 'hidden' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px', minWidth: 0 }}>
                        <img
                          src={api.getArtworkUrl('song', task.song_id, 80, 80)}
                          alt={task.title}
                          style={{
                            width: '38px',
                            height: '38px',
                            borderRadius: 'var(--radius-sm)',
                            objectFit: 'cover',
                            backgroundColor: '#16161a',
                            flexShrink: 0,
                          }}
                          onError={(e) => {
                            (e.target as HTMLImageElement).src =
                              'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="38" height="38" fill="%2316161a"><rect width="38" height="38"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="14">🎵</text></svg>';
                          }}
                        />
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div
                            style={{
                              fontWeight: 600,
                              color: '#f8fafc',
                              fontSize: '13.5px',
                              whiteSpace: 'nowrap',
                              overflow: 'hidden',
                              textOverflow: 'ellipsis',
                            }}
                            title={task.title}
                          >
                            {task.title}
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
                            title={task.artist || undefined}
                          >
                            {task.artist || 'Unknown Artist'}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td
                      style={{
                        width: '240px',
                        color: 'var(--text-secondary)',
                        fontSize: '12.5px',
                        whiteSpace: 'nowrap',
                        overflow: 'hidden',
                        textOverflow: 'ellipsis',
                      }}
                      title={task.album || undefined}
                    >
                      {task.album || '-'}
                    </td>
                    <td style={{ width: '140px', whiteSpace: 'nowrap' }}>
                      <QualityBadge quality={task.quality} isDownloaded={task.status === 'completed'} />
                    </td>
                    <td style={{ textAlign: 'right', width: '105px', whiteSpace: 'nowrap' }}>
                      {task.status === 'failed' && (
                        <Button
                          size="sm"
                          variant="secondary"
                          onClick={() => handleRetry(task.id)}
                          style={{ padding: '4px 10px', fontSize: '12px' }}
                        >
                          <RotateCcw size={12} /> Retry
                        </Button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
