import React, { useEffect, useState, useCallback } from 'react';
import { ArrowDownCircle, CheckCircle2, AlertCircle, XCircle, RotateCcw, Clock, Zap } from 'lucide-react';
import { downloadsApi } from '../../api/endpoints';
import { DownloadTask } from '../../api/types';
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

  const loadDownloads = useCallback(async () => {
    try {
      const res = await downloadsApi.getDownloads();
      if (res.success && res.data) {
        if (Array.isArray(res.data)) {
          const act = res.data.filter((d: any) =>
            ['downloading', 'in_progress', 'DOWNLOADING', 'IN_PROGRESS'].includes(d.status)
          );
          const q = res.data.filter((d: any) =>
            ['pending', 'queued', 'planned', 'QUEUED', 'PLANNED'].includes(d.status)
          );
          const hist = res.data.filter((d: any) =>
            ['completed', 'failed', 'cancelled', 'canceled', 'COMPLETED', 'FAILED', 'CANCELLED'].includes(d.status)
          );
          setActive(act);
          setQueue(q);
          setHistory(hist);
        } else {
          setActive(res.data.active || []);
          setQueue(res.data.queue || []);
          setHistory(res.data.history || []);
        }
      }
    } catch (err: any) {
      console.error('Failed to load downloads:', err);
    }
  }, []);

  useEffect(() => {
    loadDownloads();
    const interval = setInterval(loadDownloads, 3000);
    return () => clearInterval(interval);
  }, [loadDownloads]);

  // Real-time WebSocket event listener
  useEffect(() => {
    const unsub = subscribe('*', (event) => {
      const evType = (event.type || event.event || '').toLowerCase();
      if (
        evType === 'download_progress' ||
        evType === 'download.progress' ||
        evType === 'download_completed' ||
        evType === 'download.completed' ||
        evType === 'download_failed' ||
        evType === 'download.failed' ||
        evType === 'queue_updated' ||
        evType === 'queue.updated'
      ) {
        loadDownloads();
        refreshStats();
      }
    });
    return unsub;
  }, [subscribe, loadDownloads, refreshStats]);

  const handleCancel = async (taskId: number) => {
    try {
      await downloadsApi.cancelTask(taskId);
      showToast('Download cancelled', 'info');
      loadDownloads();
      refreshStats();
    } catch (err: any) {
      showToast(err.message || 'Failed to cancel download', 'error');
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

  const getStatusLabel = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'completed') return 'Downloaded';
    if (s === 'failed') return 'Failed';
    if (s === 'cancelled' || s === 'canceled') return 'Cancelled';
    return status;
  };

  return (
    <div style={{ padding: '20px 32px 32px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
      {/* 1. Header */}
      <div
        className="glass-panel"
        style={{
          padding: '14px 20px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          backgroundColor: 'var(--bg-surface)',
          border: '1px solid var(--border-subtle)',
          borderRadius: 'var(--radius-xl)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(16, 185, 129, 0.12)',
              border: '1px solid rgba(16, 185, 129, 0.22)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#10B981',
            }}
          >
            <ArrowDownCircle size={20} />
          </div>
          <div>
            <h1 className="title-display" style={{ fontSize: '20px', fontWeight: 800, margin: 0, color: '#f8fafc' }}>Downloads</h1>
            <div style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
              {active.length > 0
                ? `${active.length} active download${active.length > 1 ? 's' : ''}${queue.length > 0 ? ` · ${queue.length} in queue` : ''}`
                : queue.length > 0
                ? `${queue.length} track${queue.length > 1 ? 's' : ''} in queue`
                : 'No active downloads in queue'}
            </div>
          </div>
        </div>
      </div>

      {/* 2. Currently Downloading */}
      <div>
        <h2 className="title-display" style={{ fontSize: '13px', marginBottom: '8px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700 }}>
          Active Downloads
        </h2>
        {active.length === 0 ? (
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
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {active.map((task) => (
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
                          'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="42" height="42" fill="%2316161a"><rect width="42" height="42"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%238B7CF8" font-size="16">🎵</text></svg>';
                      }}
                    />
                    <div style={{ minWidth: 0, flex: 1 }}>
                      <div style={{ fontWeight: 600, fontSize: '14px', color: '#f8fafc', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                        {task.title}
                      </div>
                      <div style={{ fontSize: '12px', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: '2px' }}>
                        {task.artist || 'Tamil Track'} {task.album ? `· ${task.album}` : ''}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                    <QualityBadge quality={task.quality} />
                    <Button variant="ghost" size="sm" onClick={() => handleCancel(task.id)} aria-label="Cancel download" style={{ padding: '6px 10px', fontSize: '12px' }}>
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
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11.5px', color: 'var(--text-muted)' }}>
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

      {/* 3. Recently Downloaded History */}
      <div>
        <h2 className="title-display" style={{ fontSize: '13px', marginBottom: '8px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700 }}>
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
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: 'var(--color-success)', fontSize: '12px', fontWeight: 600 }}>
                          <CheckCircle2 size={14} /> Downloaded
                        </div>
                      ) : (
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '5px', color: 'var(--color-error)', fontSize: '12px', fontWeight: 600 }}>
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
                              'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="38" height="38" fill="%2316161a"><rect width="38" height="38"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%238B7CF8" font-size="14">🎵</text></svg>';
                          }}
                        />
                        <div style={{ minWidth: 0, flex: 1 }}>
                          <div
                            style={{ fontWeight: 600, color: '#f8fafc', fontSize: '13.5px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
                            title={task.title}
                          >
                            {task.title}
                          </div>
                          <div
                            style={{ fontSize: '11.5px', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: '2px' }}
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
                      {task.album || '—'}
                    </td>
                    <td style={{ width: '140px', whiteSpace: 'nowrap' }}>
                      <QualityBadge quality={task.quality} isDownloaded={task.status === 'completed'} />
                    </td>
                    <td style={{ textAlign: 'right', width: '105px', whiteSpace: 'nowrap' }}>
                      {task.status === 'failed' && (
                        <Button size="sm" variant="secondary" onClick={() => handleRetry(task.id)} style={{ padding: '4px 10px', fontSize: '12px' }}>
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
