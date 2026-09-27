import React, { useEffect, useState, useCallback } from 'react';
import { ArrowDownCircle, CheckCircle2, AlertCircle, XCircle, RotateCcw, Clock, Zap } from 'lucide-react';
import { downloadsApi } from '../../api/endpoints';
import { DownloadTask } from '../../api/types';
import { Button } from '../common/Button';
import { QualityBadge } from '../common/Badge';
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
    <div style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* 1. Header */}
      <div
        className="glass-panel"
        style={{
          padding: '16px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
        }}
      >
        <div
          style={{
            width: '38px',
            height: '38px',
            borderRadius: '10px',
            backgroundColor: 'rgba(6, 182, 212, 0.12)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <ArrowDownCircle size={20} color="var(--accent-secondary)" />
        </div>
        <div>
          <h2 className="title-display" style={{ fontSize: '18px', margin: 0 }}>Downloads</h2>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
            {active.length > 0
              ? `${active.length} currently downloading${queue.length > 0 ? ` · ${queue.length} queued` : ''}`
              : queue.length > 0
              ? `${queue.length} queued`
              : 'No active downloads'}
          </div>
        </div>
      </div>

      {/* 2. Currently Downloading */}
      <div>
        <h3 className="title-display" style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700 }}>
          Currently downloading
        </h3>
        {active.length === 0 ? (
          <div
            className="glass-panel"
            style={{ padding: '28px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '14px' }}
          >
            No active downloads. Select tracks or albums to start.
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
                  gap: '8px',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: 'var(--radius-lg)',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: '12px' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)', wordBreak: 'break-word' }}>
                      {task.title}
                    </div>
                    {task.artist && (
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                        {task.artist}
                      </div>
                    )}
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flexShrink: 0 }}>
                    <QualityBadge quality={task.quality} />
                    <Button variant="ghost" size="sm" onClick={() => handleCancel(task.id)} aria-label="Cancel download">
                      <XCircle size={14} color="var(--color-error)" /> Cancel
                    </Button>
                  </div>
                </div>

                {/* Progress Bar */}
                <div
                  style={{
                    height: '6px',
                    backgroundColor: 'rgba(255, 255, 255, 0.07)',
                    borderRadius: 'var(--radius-pill)',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${task.progress || 0}%`,
                      backgroundColor: 'var(--accent-secondary)',
                      transition: 'width 200ms ease',
                    }}
                  />
                </div>

                {/* Speed & ETA */}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)' }}>
                  <div style={{ display: 'flex', gap: '10px' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Zap size={11} color="var(--accent-secondary)" /> {task.speed_str || 'Connecting...'}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={11} /> {task.eta_str || 'Calculating...'}
                    </span>
                  </div>
                  <span style={{ fontWeight: 700, color: 'var(--text-primary)' }}>
                    {Math.round(task.progress || 0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* 3. Recently downloaded — mobile card / desktop table */}
      <div>
        <h3 className="title-display" style={{ fontSize: '14px', marginBottom: '12px', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.06em', fontWeight: 700 }}>
          Recently downloaded
        </h3>
        {history.length === 0 ? (
          <div className="glass-panel" style={{ padding: '28px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '14px' }}>
            No download history yet.
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="glass-panel desktop-only-table" style={{ overflow: 'hidden' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th style={{ width: '110px' }}>Status</th>
                    <th>Track</th>
                    <th>Artist</th>
                    <th style={{ width: '90px' }}>Quality</th>
                    <th style={{ textAlign: 'right', width: '80px' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {history.slice(0, 20).map((task) => (
                    <tr key={task.id}>
                      <td>
                        {task.status === 'completed' ? (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-success)', fontSize: '12px' }}>
                            <CheckCircle2 size={14} /> Downloaded
                          </div>
                        ) : (
                          <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-error)', fontSize: '12px' }}>
                            <AlertCircle size={14} /> Failed
                          </div>
                        )}
                      </td>
                      <td style={{ fontWeight: 600 }}>{task.title}</td>
                      <td style={{ color: 'var(--text-secondary)' }}>{task.artist || '—'}</td>
                      <td><QualityBadge quality={task.quality} /></td>
                      <td style={{ textAlign: 'right' }}>
                        {task.status === 'failed' && (
                          <Button size="sm" variant="secondary" onClick={() => handleRetry(task.id)}>
                            <RotateCcw size={12} /> Retry
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile card list */}
            <div className="glass-panel mobile-cards-container" style={{ overflow: 'hidden' }}>
              {history.slice(0, 20).map((task) => (
                <div key={task.id} className="mobile-track-card">
                  <div className="mobile-track-card__info">
                    <div className="mobile-track-card__title">{task.title}</div>
                    <div className="mobile-track-card__meta">
                      {task.artist ? `${task.artist} · ` : ''}{task.quality ? `${task.quality} kbps` : ''}
                    </div>
                    <div className="mobile-track-card__badges">
                      {task.status === 'completed' ? (
                        <span className="badge badge-success" style={{ fontSize: '10px' }}>
                          <CheckCircle2 size={10} /> Downloaded
                        </span>
                      ) : (
                        <span className="badge badge-error" style={{ fontSize: '10px' }}>
                          <AlertCircle size={10} /> Failed
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="mobile-track-card__actions">
                    {task.status === 'failed' && (
                      <button
                        className="btn-icon"
                        onClick={() => handleRetry(task.id)}
                        aria-label={`Retry ${task.title}`}
                        style={{ width: '36px', height: '36px', color: 'var(--accent-primary)' }}
                      >
                        <RotateCcw size={15} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
};
