import React, { useState } from 'react';
import { Link2, Search, CheckCircle2, Loader2, AlertCircle, ArrowRight } from 'lucide-react';
import { importsApi } from '../../api/endpoints';
import { ImportJob } from '../../api/types';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { useApp } from '../../context/AppContext';

export const ImportsView: React.FC = () => {
  const { showToast, refreshStats } = useApp();
  const [url, setUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [currentJob, setCurrentJob] = useState<ImportJob | null>(null);

  const handleStartImport = async () => {
    if (!url.trim()) {
      showToast('Please enter a Spotify or YouTube URL', 'warning');
      return;
    }

    setLoading(true);
    try {
      const res = await importsApi.startUrlImport(url.trim());
      if (res.success && res.data) {
        setCurrentJob(res.data);
        showToast('Playlist analysis initiated', 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to analyze playlist URL', 'error');
    } finally {
      setLoading(false);
    }
  };

  const getPlatformIconColor = (platform?: string) => {
    if (platform === 'spotify') return '#1db954';
    if (platform === 'youtube') return '#ff0000';
    return 'var(--accent-primary)';
  };

  return (
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '28px', maxWidth: '800px', margin: '0 auto' }}>
      {/* 1. Header */}
      <div style={{ textAlign: 'center' }}>
        <div
          style={{
            width: '56px',
            height: '56px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, #10b981 0%, #06b6d4 100%)',
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
        className="glass-panel"
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
              style={{ flex: 1, fontSize: '14px', color: 'var(--text-primary)' }}
            />
          </div>
        </div>

        <Button
          variant="primary"
          onClick={handleStartImport}
          loading={loading}
          style={{ width: '100%', padding: '12px', fontSize: '14px' }}
        >
          Analyze & Match Tracks <ArrowRight size={16} />
        </Button>
      </div>

      {/* 3. Job Status Display */}
      {currentJob && (
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
              <div
                style={{
                  width: '12px',
                  height: '12px',
                  borderRadius: '50%',
                  backgroundColor: getPlatformIconColor(currentJob.platform),
                }}
              />
              <span style={{ fontWeight: 700, fontSize: '15px', textTransform: 'capitalize' }}>
                {currentJob.platform} Import
              </span>
            </div>

            <Badge variant={currentJob.status === 'completed' ? 'success' : 'primary'}>
              {currentJob.status}
            </Badge>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', textAlign: 'center' }}>
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Total Tracks</div>
              <div className="title-display" style={{ fontSize: '20px', marginTop: '4px' }}>
                {currentJob.total_tracks}
              </div>
            </div>
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Matched</div>
              <div className="title-display" style={{ fontSize: '20px', marginTop: '4px', color: 'var(--accent-secondary)' }}>
                {currentJob.matched_tracks}
              </div>
            </div>
            <div style={{ padding: '12px', backgroundColor: 'var(--bg-surface)', borderRadius: 'var(--radius-sm)' }}>
              <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>Downloaded</div>
              <div className="title-display" style={{ fontSize: '20px', marginTop: '4px', color: 'var(--color-success)' }}>
                {currentJob.downloaded_tracks}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
