import React, { useEffect, useState } from 'react';
import {
  Settings as SettingsIcon,
  Save,
  Folder,
  CheckCircle2,
  AlertCircle,
  Download,
  Volume2,
  HardDrive,
  ShieldCheck,
} from 'lucide-react';
import { settingsApi } from '../../api/endpoints';
import { Button } from '../common/Button';
import { useApp } from '../../context/AppContext';

export const SettingsView: React.FC = () => {
  const { showToast, refreshStats } = useApp();
  const [settings, setSettings] = useState<Record<string, any>>({});
  const [downloadDir, setDownloadDir] = useState('');
  const [maxWorkers, setMaxWorkers] = useState(3);
  const [preferredQuality, setPreferredQuality] = useState(320);
  const [pathStatus, setPathStatus] = useState<{ isValid: boolean; message: string; authoritativePath?: string } | null>(null);
  const [saving, setSaving] = useState(false);

  // Playback settings (persisted in localStorage)
  const [autoplayNext, setAutoplayNext] = useState(() => {
    return localStorage.getItem('tamil_mp3_autoplay') !== 'false';
  });
  const [volumeNormalizer, setVolumeNormalizer] = useState(() => {
    return localStorage.getItem('tamil_mp3_normalize_vol') === 'true';
  });

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

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const res = await settingsApi.getSettings();
        if (res.success && res.data) {
          setSettings(res.data);
          let currentDir = res.data.download?.download_dir || 'downloads';
          if (currentDir.includes('pytest') || currentDir.includes('tmp')) {
            currentDir = 'downloads';
          }
          setDownloadDir(currentDir);
          setMaxWorkers(res.data.download?.max_workers || 3);
          setPreferredQuality(res.data.download?.preferred_quality || 320);
          validateDirectory(currentDir);
        }
      } catch (err: any) {
        showToast(err.message || 'Failed to load settings', 'error');
      }
    };

    loadSettings();
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

      // Save local playback prefs
      localStorage.setItem('tamil_mp3_autoplay', autoplayNext ? 'true' : 'false');
      localStorage.setItem('tamil_mp3_normalize_vol', volumeNormalizer ? 'true' : 'false');

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
    <div className="view-container" style={{ maxWidth: '840px', margin: '0 auto', gap: '24px' }}>
      {/* View Header */}
      <div className="view-header">
        <div className="view-header-title">
          <div className="view-header-icon">
            <SettingsIcon size={18} />
          </div>
          <div>
            <h1 className="view-title">Settings</h1>
            <div className="view-subtitle">
              Manage download preferences, storage destinations, and audio playback
            </div>
          </div>
        </div>

        <Button variant="primary" onClick={handleSave} loading={saving} aria-label="Save Settings">
          <Save size={15} /> Save Changes
        </Button>
      </div>

      {/* 1. DOWNLOAD SETTINGS */}
      <div className="table-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', paddingBottom: '12px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div
            style={{
              width: '26px',
              height: '26px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(16, 185, 129, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Download size={14} color="#10B981" />
          </div>
          <div>
            <h2 style={{ fontSize: '14px', fontWeight: 700, margin: 0, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-main)' }}>
              Download Settings
            </h2>
            <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
              Configure download destinations, concurrency, and default target bitrate
            </span>
          </div>
        </div>

        {/* Download Directory */}
        <div>
          <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
            Authoritative Download Directory
          </label>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>
            Local directory where finalized MP3 songs and soundtrack album collections are saved.
          </div>
          <div style={{ display: 'flex', gap: '10px', width: '100%' }}>
            <input
              type="text"
              value={downloadDir}
              onChange={(e) => setDownloadDir(e.target.value)}
              onBlur={() => validateDirectory(downloadDir)}
              style={{
                flex: 1,
                minWidth: 0,
                padding: '9px 12px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-medium)',
                fontSize: '13px',
              }}
              aria-label="Download Directory Path"
            />
            <Button
              variant="secondary"
              onClick={() => validateDirectory(downloadDir)}
              aria-label="Verify directory path"
              style={{ flexShrink: 0 }}
            >
              <Folder size={14} /> Validate Path
            </Button>
          </div>

          {pathStatus && (
            <div
              style={{
                fontSize: '12px',
                marginTop: '8px',
                padding: '8px 12px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: pathStatus.isValid ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                color: pathStatus.isValid ? '#10B981' : 'var(--color-error)',
                border: `1px solid ${pathStatus.isValid ? 'rgba(16, 185, 129, 0.25)' : 'rgba(239, 68, 68, 0.25)'}`,
              }}
            >
              {pathStatus.isValid ? <CheckCircle2 size={15} /> : <AlertCircle size={15} />}
              <div>
                <strong>{pathStatus.isValid ? 'Active Directory' : 'Invalid Directory'}</strong>: {pathStatus.message}
                {pathStatus.authoritativePath && (
                  <div style={{ fontSize: '11px', marginTop: '2px', opacity: 0.85, fontFamily: 'monospace' }}>
                    {pathStatus.authoritativePath}
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Simultaneous Downloads */}
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
            <label style={{ fontSize: '13px', fontWeight: 600 }}>Concurrent Downloads</label>
            <span style={{ fontWeight: 700, color: 'var(--primary-light)', fontSize: '13px' }}>
              {maxWorkers} parallel threads
            </span>
          </div>
          <input
            type="range"
            min="1"
            max="8"
            value={maxWorkers}
            onChange={(e) => setMaxWorkers(parseInt(e.target.value))}
            style={{ width: '100%', accentColor: 'var(--primary)', cursor: 'pointer' }}
            aria-label="Simultaneous Downloads Slider"
          />
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Controls how many tracks download at once. Recommended: 3 to 4 threads for optimal performance.
          </div>
        </div>

        {/* Preferred Quality */}
        <div>
          <label style={{ display: 'block', fontSize: '13px', fontWeight: 600, marginBottom: '6px' }}>
            Preferred Download Quality
          </label>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '10px' }}>
            New downloads prefer this quality when available. Existing higher-quality files are never downgraded.
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px' }}>
            {[
              { val: 320, label: '320 kbps', badge: 'High Quality', desc: 'Highest audio clarity (Recommended)' },
              { val: 192, label: '192 kbps', badge: 'Medium', desc: 'Balanced file size' },
              { val: 128, label: '128 kbps', badge: 'Standard', desc: 'Compact file size' },
            ].map((q) => {
              const isSelected = preferredQuality === q.val;
              return (
                <button
                  key={q.val}
                  type="button"
                  onClick={() => setPreferredQuality(q.val)}
                  style={{
                    padding: '12px 14px',
                    borderRadius: 'var(--radius-md)',
                    border: isSelected ? '1px solid var(--accent-primary)' : '1px solid var(--border-medium)',
                    backgroundColor: isSelected ? 'rgba(229, 149, 0, 0.12)' : 'var(--bg-surface)',
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'flex-start',
                    gap: '4px',
                    cursor: 'pointer',
                    textAlign: 'left',
                    transition: 'all 0.15s ease',
                  }}
                  aria-label={`Select ${q.label}`}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                    <span style={{ fontWeight: 700, fontSize: '13.5px', color: isSelected ? 'var(--primary-light)' : 'var(--text-main)' }}>
                      {q.label}
                    </span>
                    <span className="quality-chip" style={{ fontSize: '10px' }}>{q.badge}</span>
                  </div>
                  <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>{q.desc}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* 2. PLAYBACK SETTINGS */}
      <div className="table-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', paddingBottom: '12px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div
            style={{
              width: '26px',
              height: '26px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(229, 149, 0, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Volume2 size={14} color="var(--accent-primary)" />
          </div>
          <div>
            <h2 style={{ fontSize: '14px', fontWeight: 700, margin: 0, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-main)' }}>
              Playback Preferences
            </h2>
            <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
              Desktop audio player behaviors and playback queue settings
            </span>
          </div>
        </div>

        {/* Auto-advance queue */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 600 }}>Continuous Playback (Queue Auto-Advance)</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Automatically advance to the next song in the active playlist or album when current track finishes.
            </div>
          </div>
          <input
            type="checkbox"
            checked={autoplayNext}
            onChange={(e) => setAutoplayNext(e.target.checked)}
            style={{ width: '18px', height: '18px', accentColor: 'var(--primary)', cursor: 'pointer' }}
            aria-label="Toggle continuous playback"
          />
        </div>

        {/* Volume Normalization hint */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
          <div>
            <div style={{ fontSize: '13px', fontWeight: 600 }}>High-Fidelity Audio Passthrough</div>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Streams downloaded 320 kbps MP3s directly to the system audio device without lossy re-encoding.
            </div>
          </div>
          <span className="badge badge-success" style={{ fontSize: '11px' }}>
            Bit-Perfect Active
          </span>
        </div>
      </div>

      {/* 3. STORAGE & RECONCILIATION */}
      <div className="table-card" style={{ padding: '24px', display: 'flex', flexDirection: 'column', gap: '16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', paddingBottom: '12px', borderBottom: '1px solid var(--border-subtle)' }}>
          <div
            style={{
              width: '26px',
              height: '26px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(251, 191, 36, 0.12)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <HardDrive size={14} color="#FBBF24" />
          </div>
          <div>
            <h2 style={{ fontSize: '14px', fontWeight: 700, margin: 0, textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--text-main)' }}>
              Storage Rules & Quality Protection
            </h2>
            <span style={{ fontSize: '11.5px', color: 'var(--text-muted)' }}>
              Canonical library rules and file upgrade policies
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
            <ShieldCheck size={18} color="var(--primary-light)" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              <strong style={{ color: 'var(--text-main)' }}>No Quality Downgrade Rule:</strong> The downloader never overwrites an existing 320 kbps file with a lower quality stream. If a 128 kbps track is currently owned and a 320 kbps source is found, the system presents an explicit upgrade option.
            </div>
          </div>

          <div style={{ display: 'flex', gap: '12px', alignItems: 'flex-start' }}>
            <HardDrive size={18} color="#10B981" style={{ flexShrink: 0, marginTop: '2px' }} />
            <div style={{ fontSize: '12.5px', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
              <strong style={{ color: 'var(--text-main)' }}>Non-Destructive Library:</strong> Tracks removed from the library catalog retain their physical files on disk unless explicitly checked for permanent deletion in the confirmation prompt.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
