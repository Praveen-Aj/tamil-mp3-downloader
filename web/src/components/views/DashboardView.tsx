import React, { useEffect, useState } from 'react';
import {
  Music,
  CheckCircle2,
  Film,
  Users,
  HardDrive,
  Flame,
  ArrowDownCircle,
  Radio,
  ExternalLink,
  Play,
} from 'lucide-react';
import { useApp } from '../../context/AppContext';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { systemApi, songsApi } from '../../api/endpoints';
import { RegisteredSource, Song } from '../../api/types';
import { useAudioPlayer } from '../../context/AudioPlayerContext';

export const DashboardView: React.FC = () => {
  const { stats, navigateTo } = useApp();
  const { playSong } = useAudioPlayer();
  const [sources, setSources] = useState<RegisteredSource[]>([]);
  const [recentSongs, setRecentSongs] = useState<Song[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadDashboard = async () => {
      try {
        const [srcRes, songsRes] = await Promise.all([
          systemApi.getSources(),
          songsApi.getSongs({ page_size: 5, sort_by: 'id', sort_order: 'desc' }),
        ]);

        if (srcRes.success && srcRes.data) {
          setSources(srcRes.data.sources || []);
        }
        if (songsRes.success && songsRes.data) {
          setRecentSongs(songsRes.data.items || []);
        }
      } catch (err) {
        console.error('Failed to load dashboard data:', err);
      } finally {
        setLoading(false);
      }
    };
    loadDashboard();
  }, []);

  const formatBytes = (bytes?: number) => {
    if (!bytes) return '0 MB';
    const mb = bytes / (1024 * 1024);
    if (mb > 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${Math.round(mb)} MB`;
  };

  return (
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '32px' }}>
      {/* 1. Hero Greeting & Quick Actions */}
      <div
        className="glass-panel"
        style={{
          padding: '28px 32px',
          background: 'linear-gradient(135deg, rgba(30, 27, 75, 0.6) 0%, rgba(17, 26, 46, 0.8) 100%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div>
          <h2 className="title-display text-gradient" style={{ fontSize: '26px', fontWeight: 800 }}>
            Tamil MP3 Music Studio
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: '6px', fontSize: '14px', maxWidth: '600px' }}>
            Explore master-quality soundtracks, top charts, and lossless downloads with unified filesystem integrity.
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <Button variant="primary" onClick={() => navigateTo('songs')}>
            <Music size={16} /> Explore Library
          </Button>
          <Button variant="secondary" onClick={() => navigateTo('imports')}>
            <ExternalLink size={16} /> Import URL
          </Button>
        </div>
      </div>

      {/* 2. Key Metrics Grid */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        <Card onClick={() => navigateTo('songs')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Total Songs</span>
            <Music size={18} color="var(--accent-primary)" />
          </div>
          <div className="title-display" style={{ fontSize: '28px', marginTop: '10px' }}>
            {stats?.total_songs ?? 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--color-success)', marginTop: '4px' }}>
            {stats?.total_owned ?? 0} downloaded on disk
          </div>
        </Card>

        <Card onClick={() => navigateTo('movies')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Movies</span>
            <Film size={18} color="var(--accent-secondary)" />
          </div>
          <div className="title-display" style={{ fontSize: '28px', marginTop: '10px' }}>
            {stats?.total_movies ?? 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Original soundtrack albums
          </div>
        </Card>

        <Card onClick={() => navigateTo('artists')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Artists</span>
            <Users size={18} color="#f59e0b" />
          </div>
          <div className="title-display" style={{ fontSize: '28px', marginTop: '10px' }}>
            {stats?.total_artists ?? 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Singers, lyricists, composers
          </div>
        </Card>

        <Card onClick={() => navigateTo('charts')}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Top Charts</span>
            <Flame size={18} color="#f43f5e" />
          </div>
          <div className="title-display" style={{ fontSize: '28px', marginTop: '10px' }}>
            {stats?.total_charts ?? 0}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Weekly & monthly rankings
          </div>
        </Card>

        <Card>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Verified Storage</span>
            <HardDrive size={18} color="#10b981" />
          </div>
          <div className="title-display" style={{ fontSize: '28px', marginTop: '10px' }}>
            {formatBytes(stats?.total_storage_bytes)}
          </div>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Physical audio on filesystem
          </div>
        </Card>
      </div>

      {/* 3. Two Columns: Recent Tracks & Sources Health */}
      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '24px' }}>
        {/* Recent Additions */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
            <h3 className="title-display" style={{ fontSize: '16px' }}>Recently Added Songs</h3>
            <Button variant="ghost" size="sm" onClick={() => navigateTo('songs')}>
              View All
            </Button>
          </div>

          {recentSongs.length === 0 ? (
            <div style={{ color: 'var(--text-muted)', padding: '20px 0', textAlign: 'center' }}>
              No songs added yet. Import a Spotify playlist or browse movies!
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {recentSongs.map((s) => (
                <div
                  key={s.id}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: 'rgba(255, 255, 255, 0.02)',
                    border: '1px solid var(--border-subtle)',
                    transition: 'all var(--transition-fast)',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                  onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.02)')}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <button
                      onClick={() => playSong(s)}
                      className="btn-icon"
                      style={{ width: '32px', height: '32px', backgroundColor: 'rgba(255, 255, 255, 0.06)' }}
                    >
                      <Play size={14} fill="currentColor" />
                    </button>
                    <div>
                      <div style={{ fontWeight: 600, fontSize: '13px' }}>{s.title}</div>
                      <div style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                        {s.artist || s.album || 'Unknown'} {s.year ? `• ${s.year}` : ''}
                      </div>
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <Badge variant={s.state === 'OWNED' ? 'success' : 'primary'}>
                      {s.state === 'OWNED' ? 'Downloaded' : 'Available'}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Music Sources Health */}
        <div className="glass-panel" style={{ padding: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
            <Radio size={16} color="var(--accent-secondary)" />
            <h3 className="title-display" style={{ fontSize: '16px' }}>Scraper Providers</h3>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
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
                    {src.name}
                  </div>
                </div>

                <Badge variant={src.enabled ? (src.is_usable ? 'success' : 'warning') : 'subtle'}>
                  {src.enabled ? (src.is_usable ? 'Active' : 'Degraded') : 'Disabled'}
                </Badge>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
