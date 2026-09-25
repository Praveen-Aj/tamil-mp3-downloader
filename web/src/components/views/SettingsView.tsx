import React, { useEffect, useState } from 'react';
import {
  Settings as SettingsIcon,
  Save,
  Folder,
  CheckCircle2,
  AlertCircle,
  Activity,
  ChevronDown,
  ChevronUp,
  Cpu,
  Radio,
  HardDrive,
  RefreshCw,
} from 'lucide-react';
import { settingsApi, systemApi } from '../../api/endpoints';
import { RegisteredSource, SystemStats } from '../../api/types';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { useApp } from '../../context/AppContext';

export const SettingsView: React.FC = () => {
  const { showToast, refreshStats, isBackendHealthy } = useApp();
  const [settings, setSettings] = useState<Record<string, any>>({});
  const [downloadDir, setDownloadDir] = useState('');
  const [maxWorkers, setMaxWorkers] = useState(3);
  const [preferredQuality, setPreferredQuality] = useState(320);
  const [pathStatus, setPathStatus] = useState<{ isValid: boolean; message: string; authoritativePath?: string } | null>(null);
  const [saving, setSaving] = useState(false);

  // Engine Diagnostics State
  const [diagnosticsOpen, setDiagnosticsOpen] = useState(true);
  const [sources, setSources] = useState<RegisteredSource[]>([]);
  const [loadingSources, setLoadingSources] = useState(false);

  const validateDirectory = async (dirPath: string) => {
    if (!dirPath) return;
    try {
      const res = await settingsApi.validatePath(dirPath);
      if (res.success && res.data) {
        setPathStatus({
          isValid: res.data.is_valid,
          message: res.data.message,
          authoritativePath: res.data.resolved_path,
        });
      }
    } catch (err: any) {
      setPathStatus({ isValid: false, message: 'Invalid directory path' });
    }
  };

  const loadSources = async () => {
    setLoadingSources(true);
    try {
      const res = await systemApi.getSources();
      if (res.success && res.data) {
        setSources(res.data.sources || []);
      }
    } catch (err) {
      console.error('Failed to load scraper sources:', err);
    } finally {
      setLoadingSources(false);
    }
  };

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const res = await settingsApi.getSettings();
        if (res.success && res.data) {
          setSettings(res.data);
          const currentDir = res.data.download?.download_dir || 'downloads';
          setDownloadDir(currentDir);
          setMaxWorkers(res.data.download?.max_workers || 3);
          setPreferredQuality(res.data.download?.preferred_quality || 320);
          // Immediately validate directory so user sees verified status
          validateDirectory(currentDir);
        }
      } catch (err: any) {
        showToast(err.message || 'Failed to load settings', 'error');
      }
    };

    loadSettings();
    loadSources();
  }, [showToast]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = {
        ...settings,
        download: {
          ...settings.download,
          download_dir: downloadDir,
          max_workers: maxWorkers,
          preferred_quality: preferredQuality,
        },
      };
      await settingsApi.updateSettings(updated);
      showToast('Settings saved successfully', 'success');
      refreshStats();
      validateDirectory(downloadDir);
    } catch (err: any) {
      showToast(err.message || 'Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: '32px', maxWidth: '780px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '28px' }}>
      {/* View Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
        <div
          style={{
            width: '42px',
            height: '42px',
            borderRadius: '12px',
            backgroundColor: 'rgba(99, 102, 241, 0.15)',
            border: '1px solid rgba(99, 102, 241, 0.3)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--accent-primary)',
          }}
        >
          <SettingsIcon size={22} />
        </div>
        <div>
          <h2 className="title-display" style={{ fontSize: '22px', margin: 0 }}>
            Application & Engine Settings
          </h2>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)', marginTop: '2px' }}>
            Configure download concurrency, authoritative storage directories, audio defaults, and engine health
          </div>
        </div>
      </div>

      {/* Main Download Settings Card */}
      <div className="glass-panel" style={{ padding: '28px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <h3 className="title-display" style={{ fontSize: '16px', margin: 0, borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px' }}>
          Download Settings
        </h3>

        {/* Download Directory */}
        <div>
          <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
            Download Directory Path
          </label>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '10px' }}>
            Authoritative folder on your filesystem where verified MP3 audio files and soundtrack albums are saved.
          </div>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input
              type="text"
              value={downloadDir}
              onChange={(e) => setDownloadDir(e.target.value)}
              onBlur={() => validateDirectory(downloadDir)}
              style={{
                flex: 1,
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-medium)',
                fontSize: '13px',
              }}
              aria-label="Download Directory Path"
            />
            <Button variant="secondary" onClick={() => validateDirectory(downloadDir)} aria-label="Verify directory path">
              <Folder size={15} /> Validate Path
            </Button>
          </div>

          {pathStatus && (
            <div
              style={{
                fontSize: '12px',
                marginTop: '8px',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: pathStatus.isValid ? 'var(--color-success-bg)' : 'var(--color-error-bg)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                color: pathStatus.isValid ? 'var(--color-success)' : 'var(--color-error)',
              }}
            >
              {pathStatus.isValid ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
              <div>
                <strong>{pathStatus.isValid ? 'Valid Authoritative Directory' : 'Invalid Directory'}</strong>: {pathStatus.message}
                {pathStatus.authoritativePath && (
                  <div style={{ fontSize: '11px', marginTop: '2px', opacity: 0.9 }}>
                    Resolved: {pathStatus.authoritativePath}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Simultaneous Downloads */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: 600 }}>Simultaneous Downloads (Max Concurrency)</label>
            <span style={{ fontWeight: 700, color: 'var(--accent-primary)', fontSize: '14px' }}>
              {maxWorkers} concurrent downloads
            </span>
          </div>
          <input
            type="range"
            min="1"
            max="8"
            value={maxWorkers}
            onChange={(e) => setMaxWorkers(parseInt(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--accent-primary)', cursor: 'pointer' }}
            aria-label="Simultaneous Downloads Slider"
          />
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '6px' }}>
            Number of audio tracks to download in parallel. Recommended: 3 to 4 threads.
          </div>
        </div>

        {/* Preferred Quality */}
        <div>
          <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
            Preferred Quality (Target Bitrate)
          </label>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '10px' }}>
            The engine automatically prioritizes this bitrate when resolving multi-source albums and tracks. Existing files are upgraded when a higher quality source becomes available.
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            {[
              { val: 320, label: '320 kbps', desc: 'High Quality (Recommended)' },
              { val: 192, label: '192 kbps', desc: 'Medium Quality' },
              { val: 128, label: '128 kbps', desc: 'Standard Quality' },
            ].map((q) => (
              <button
                key={q.val}
                type="button"
                onClick={() => setPreferredQuality(q.val)}
                className={`btn ${preferredQuality === q.val ? 'btn-primary' : 'btn-secondary'}`}
                style={{ flex: 1, padding: '12px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '4px' }}
                aria-label={`Select ${q.label}`}
              >
                <span style={{ fontWeight: 700, fontSize: '14px' }}>{q.label}</span>
                <span style={{ fontSize: '10px', opacity: 0.85 }}>{q.desc}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Save Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
          <Button variant="primary" onClick={handleSave} loading={saving} aria-label="Save Settings">
            <Save size={16} /> Save Settings
          </Button>
        </div>
      </div>

      {/* Engine Diagnostics & Scraper Health Accordion */}
      <div className="glass-panel" style={{ overflow: 'hidden' }}>
        <button
          onClick={() => setDiagnosticsOpen(!diagnosticsOpen)}
          style={{
            width: '100%',
            padding: '20px 24px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            background: 'none',
            border: 'none',
            color: 'var(--text-primary)',
            cursor: 'pointer',
            textAlign: 'left',
          }}
          aria-expanded={diagnosticsOpen}
          aria-label="Toggle Engine Diagnostics"
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Activity size={18} color="var(--accent-secondary)" />
            <div>
              <div style={{ fontWeight: 700, fontSize: '15px' }}>Engine Diagnostics & Scraper Health</div>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Provider status, circuit breakers, and backend service connectivity
              </div>
            </div>
          </div>
          {diagnosticsOpen ? <ChevronUp size={18} /> : <ChevronDown size={18} />}
        </button>

        {diagnosticsOpen && (
          <div style={{ padding: '0 24px 24px', display: 'flex', flexDirection: 'column', gap: '16px', borderTop: '1px solid var(--border-subtle)' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', paddingTop: '16px' }}>
              <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                Active Scraper Adapters ({sources.length})
              </div>
              <button
                onClick={loadSources}
                className="btn-icon"
                style={{ width: '28px', height: '28px' }}
                title="Refresh scraper status"
                aria-label="Refresh scraper health"
              >
                <RefreshCw size={13} className={loadingSources ? 'animate-spin' : ''} />
              </button>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' }}>
              {sources.map((src) => (
                <div
                  key={src.name}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-subtle)',
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 600, fontSize: '13px' }}>{src.display_name}</div>
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
                      Provider: {src.name} • Priority: {src.priority ?? 'normal'}
                    </div>
                  </div>

                  <Badge variant={src.enabled ? (src.is_usable ? 'success' : 'warning') : 'subtle'}>
                    {src.enabled ? (src.is_usable ? 'Healthy' : 'Degraded') : 'Disabled'}
                  </Badge>
                </div>
              ))}
            </div>

            {/* Backend connectivity check */}
            <div
              style={{
                marginTop: '10px',
                padding: '12px 16px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'rgba(0, 0, 0, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                fontSize: '12px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <Cpu size={15} color="var(--accent-primary)" />
                <span>FastAPI Microservice Engine: <strong>{isBackendHealthy ? 'Online (Port 8000)' : 'Unreachable'}</strong></span>
              </div>
              <span style={{ color: 'var(--text-muted)' }}>SQLite V6 Canonical Storage</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
