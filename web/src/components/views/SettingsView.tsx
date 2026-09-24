import React, { useEffect, useState } from 'react';
import { Settings as SettingsIcon, Save, Folder, CheckCircle2, AlertCircle } from 'lucide-react';
import { settingsApi } from '../../api/endpoints';
import { Button } from '../common/Button';
import { useApp } from '../../context/AppContext';

export const SettingsView: React.FC = () => {
  const { showToast } = useApp();
  const [settings, setSettings] = useState<Record<string, any>>({});
  const [downloadDir, setDownloadDir] = useState('');
  const [maxWorkers, setMaxWorkers] = useState(3);
  const [preferredQuality, setPreferredQuality] = useState(320);
  const [pathStatus, setPathStatus] = useState<{ isValid: boolean; message: string } | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const res = await settingsApi.getSettings();
        if (res.success && res.data) {
          setSettings(res.data);
          setDownloadDir(res.data.download?.download_dir || 'downloads');
          setMaxWorkers(res.data.download?.max_workers || 3);
          setPreferredQuality(res.data.download?.preferred_quality || 320);
        }
      } catch (err: any) {
        showToast(err.message || 'Failed to load settings', 'error');
      }
    };
    loadSettings();
  }, [showToast]);

  const handleValidatePath = async () => {
    try {
      const res = await settingsApi.validatePath(downloadDir);
      if (res.success && res.data) {
        setPathStatus({ isValid: res.data.is_valid, message: res.data.message });
      }
    } catch (err: any) {
      setPathStatus({ isValid: false, message: 'Invalid directory path' });
    }
  };

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
    } catch (err: any) {
      showToast(err.message || 'Failed to save settings', 'error');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div style={{ padding: '32px', maxWidth: '720px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div
          style={{
            width: '40px',
            height: '40px',
            borderRadius: '10px',
            backgroundColor: 'rgba(255, 255, 255, 0.08)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <SettingsIcon size={22} color="var(--text-primary)" />
        </div>
        <div>
          <h2 className="title-display" style={{ fontSize: '20px' }}>Application Settings</h2>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Configure download concurrency, target storage, and audio defaults
          </div>
        </div>
      </div>

      <div className="glass-panel" style={{ padding: '28px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Download Directory */}
        <div>
          <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>
            Download Directory
          </label>
          <div style={{ display: 'flex', gap: '10px' }}>
            <input
              type="text"
              value={downloadDir}
              onChange={(e) => setDownloadDir(e.target.value)}
              onBlur={handleValidatePath}
              style={{
                flex: 1,
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-medium)',
              }}
            />
            <Button variant="secondary" onClick={handleValidatePath}>
              <Folder size={15} /> Check Path
            </Button>
          </div>
          {pathStatus && (
            <div
              style={{
                fontSize: '12px',
                marginTop: '6px',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                color: pathStatus.isValid ? 'var(--color-success)' : 'var(--color-error)',
              }}
            >
              {pathStatus.isValid ? <CheckCircle2 size={14} /> : <AlertCircle size={14} />}
              {pathStatus.message}
            </div>
          )}
        </div>

        {/* Max Concurrent Workers */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
            <label style={{ fontSize: '13px', fontWeight: 600 }}>Concurrent Download Threads</label>
            <span style={{ fontWeight: 700, color: 'var(--accent-primary)' }}>{maxWorkers} workers</span>
          </div>
          <input
            type="range"
            min="1"
            max="8"
            value={maxWorkers}
            onChange={(e) => setMaxWorkers(parseInt(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--accent-primary)', cursor: 'pointer' }}
          />
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Balances download speed against host CPU and network socket limits.
          </div>
        </div>

        {/* Preferred Quality */}
        <div>
          <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '8px' }}>
            Default Preferred Audio Bitrate
          </label>
          <div style={{ display: 'flex', gap: '12px' }}>
            {[320, 192, 128].map((q) => (
              <button
                key={q}
                type="button"
                onClick={() => setPreferredQuality(q)}
                className={`btn ${preferredQuality === q ? 'btn-primary' : 'btn-secondary'}`}
                style={{ flex: 1, padding: '10px' }}
              >
                {q} KBPS {q === 320 ? '(Highest Quality)' : ''}
              </button>
            ))}
          </div>
        </div>

        {/* Save Button */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: '12px', borderTop: '1px solid var(--border-subtle)' }}>
          <Button variant="primary" onClick={handleSave} loading={saving}>
            <Save size={16} /> Save Changes
          </Button>
        </div>
      </div>
    </div>
  );
};
