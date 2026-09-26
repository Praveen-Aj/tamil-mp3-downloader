import React, { useEffect, useState, useCallback } from 'react';
import { ArrowDownCircle, CheckCircle2, AlertCircle, XCircle, RotateCcw, Clock, Zap } from 'lucide-react';
import { downloadsApi } from '../../api/endpoints';
import { DownloadTask } from '../../api/types';
import { Button } from '../common/Button';
import { QualityBadge, Badge } from '../common/Badge';
import { useApp } from '../../context/AppContext';
import { useWebSocket } from '../../context/WebSocketContext';

export const DownloadsView: React.FC = () => {
  const { showToast, refreshStats } = useApp();
  const { subscribe } = useWebSocket();

  const [active, setActive] = useState<DownloadTask[]>([]);
  const [queue, setQueue] = useState<DownloadTask[]>([]);
  const [history, setHistory] = useState<DownloadTask[]>([]);
  const [loading, setLoading] = useState(false);

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

  return (
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* 1. Header Bar */}
      <div
        className="glass-panel"
        style={{
          padding: '20px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              backgroundColor: 'rgba(6, 182, 212, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <ArrowDownCircle size={22} color="var(--accent-secondary)" />
          </div>
          <div>
            <h2 className="title-display" style={{ fontSize: '18px' }}>Download Engine</h2>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Active downloads: {active.length} • Queued: {queue.length}
            </div>
          </div>
        </div>
      </div>

      {/* 2. Active Downloads */}
      <div>
        <h3 className="title-display" style={{ fontSize: '16px', marginBottom: '14px', color: 'var(--text-primary)' }}>
          Active Transfers ({active.length})
        </h3>
        {active.length === 0 ? (
          <div
            className="glass-panel"
            style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}
          >
            No active downloads right now. Select tracks or albums to download!
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {active.map((task) => (
              <div
                key={task.id}
                className="glass-panel"
                style={{
                  padding: '16px 20px',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: '10px',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <div>
                    <span style={{ fontWeight: 600, fontSize: '14px', color: 'var(--text-primary)' }}>
                      {task.title}
                    </span>
                    <span style={{ fontSize: '12px', color: 'var(--text-muted)', marginLeft: '8px' }}>
                      {task.artist || task.source_name}
                    </span>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <QualityBadge quality={task.quality} />
                    <Button variant="ghost" size="sm" onClick={() => handleCancel(task.id)}>
                      <XCircle size={15} color="var(--color-error)" /> Cancel
                    </Button>
                  </div>
                </div>

                {/* Progress Bar */}
                <div
                  style={{
                    height: '8px',
                    backgroundColor: 'rgba(255, 255, 255, 0.08)',
                    borderRadius: 'var(--radius-pill)',
                    overflow: 'hidden',
                  }}
                >
                  <div
                    style={{
                      height: '100%',
                      width: `${task.progress || 0}%`,
                      backgroundColor: 'var(--accent-secondary)',
                      boxShadow: '0 0 10px var(--accent-secondary-glow)',
                      transition: 'width 200ms ease',
                    }}
                  />
                </div>

                {/* Speed & ETA */}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', color: 'var(--text-muted)' }}>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Zap size={12} color="var(--accent-secondary)" /> {task.speed_str || 'Connecting...'}
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                      <Clock size={12} /> ETA: {task.eta_str || 'Calculating...'}
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

      {/* 3. History List */}
      <div>
        <h3 className="title-display" style={{ fontSize: '16px', marginBottom: '14px', color: 'var(--text-primary)' }}>
          Recent Download History ({history.length})
        </h3>
        {history.length === 0 ? (
          <div className="glass-panel" style={{ padding: '32px', textAlign: 'center', color: 'var(--text-muted)' }}>
            No completed or past downloads recorded.
          </div>
        ) : (
          <div className="glass-panel" style={{ overflow: 'hidden' }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Status</th>
                  <th>Track Title</th>
                  <th>Artist</th>
                  <th>Quality</th>
                  <th>Source</th>
                  <th style={{ textAlign: 'right' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {history.slice(0, 15).map((task) => (
                  <tr key={task.id}>
                    <td>
                      {task.status === 'completed' ? (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-success)', fontSize: '12px' }}>
                          <CheckCircle2 size={16} /> Completed
                        </div>
                      ) : (
                        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', color: 'var(--color-error)', fontSize: '12px' }}>
                          <AlertCircle size={16} /> Failed
                        </div>
                      )}
                    </td>
                    <td style={{ fontWeight: 600 }}>{task.title}</td>
                    <td style={{ color: 'var(--text-secondary)' }}>{task.artist || '—'}</td>
                    <td>
                      <QualityBadge quality={task.quality} />
                    </td>
                    <td style={{ textTransform: 'capitalize', color: 'var(--text-muted)' }}>
                      {task.source_name}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      {task.status === 'failed' && (
                        <Button size="sm" variant="secondary" onClick={() => handleRetry(task.id)}>
                          <RotateCcw size={13} /> Retry
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
