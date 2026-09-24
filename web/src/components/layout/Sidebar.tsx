import React from 'react';
import {
  LayoutDashboard,
  Music,
  Film,
  Users,
  Flame,
  ListMusic,
  ArrowDownCircle,
  Link2,
  Settings,
  Radio,
} from 'lucide-react';
import { useApp, ViewType } from '../../context/AppContext';

interface NavItem {
  id: ViewType;
  label: string;
  icon: React.ReactNode;
  badge?: number;
}

export const Sidebar: React.FC = () => {
  const { currentView, navigateTo, stats, isBackendHealthy } = useApp();

  const navItems: NavItem[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={18} /> },
    { id: 'songs', label: 'Songs', icon: <Music size={18} />, badge: stats?.total_songs },
    { id: 'movies', label: 'Movies', icon: <Film size={18} />, badge: stats?.total_movies },
    { id: 'artists', label: 'Artists', icon: <Users size={18} />, badge: stats?.total_artists },
    { id: 'charts', label: 'Charts', icon: <Flame size={18} /> },
    { id: 'playlists', label: 'Playlists', icon: <ListMusic size={18} />, badge: stats?.total_playlists },
    {
      id: 'downloads',
      label: 'Downloads',
      icon: <ArrowDownCircle size={18} />,
      badge: stats?.active_downloads ? stats.active_downloads : undefined,
    },
    { id: 'imports', label: 'Import Music', icon: <Link2 size={18} /> },
    { id: 'settings', label: 'Settings', icon: <Settings size={18} /> },
  ];

  return (
    <aside
      style={{
        width: 'var(--sidebar-width)',
        height: '100%',
        backgroundColor: 'var(--bg-sidebar)',
        borderRight: '1px solid var(--border-subtle)',
        display: 'flex',
        flexDirection: 'column',
        flexShrink: 0,
        userSelect: 'none',
      }}
    >
      {/* Brand Header */}
      <div
        style={{
          padding: '24px 20px 20px',
          display: 'flex',
          alignItems: 'center',
          gap: '12px',
          borderBottom: '1px solid var(--border-subtle)',
        }}
      >
        <div
          style={{
            width: '36px',
            height: '36px',
            borderRadius: '10px',
            background: 'linear-gradient(135deg, #6366f1 0%, #06b6d4 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(99, 102, 241, 0.35)',
          }}
        >
          <Radio size={20} color="#ffffff" />
        </div>
        <div>
          <div
            className="title-display text-gradient"
            style={{ fontSize: '16px', fontWeight: 800, lineHeight: 1.1 }}
          >
            TAMIL MP3
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', fontWeight: 500 }}>
            STUDIO V6
          </div>
        </div>
      </div>

      {/* Navigation Menu */}
      <nav style={{ padding: '16px 12px', flex: 1, overflowY: 'auto' }}>
        <div
          style={{
            fontSize: '11px',
            fontWeight: 600,
            textTransform: 'uppercase',
            letterSpacing: '0.06em',
            color: 'var(--text-muted)',
            padding: '0 12px 8px',
          }}
        >
          Library
        </div>
        <ul style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {navItems.map((item) => {
            const isActive = currentView === item.id;
            return (
              <li key={item.id}>
                <button
                  onClick={() => navigateTo(item.id)}
                  style={{
                    width: '100%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    padding: '10px 14px',
                    borderRadius: 'var(--radius-md)',
                    backgroundColor: isActive ? 'var(--accent-primary)' : 'transparent',
                    color: isActive ? '#ffffff' : 'var(--text-secondary)',
                    fontWeight: isActive ? 600 : 500,
                    fontSize: '13px',
                    boxShadow: isActive ? '0 4px 12px var(--accent-primary-glow)' : 'none',
                    transition: 'all var(--transition-fast)',
                  }}
                  onMouseEnter={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)';
                      e.currentTarget.style.color = 'var(--text-primary)';
                    }
                  }}
                  onMouseLeave={(e) => {
                    if (!isActive) {
                      e.currentTarget.style.backgroundColor = 'transparent';
                      e.currentTarget.style.color = 'var(--text-secondary)';
                    }
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    {item.icon}
                    <span>{item.label}</span>
                  </div>
                  {item.badge !== undefined && item.badge > 0 && (
                    <span
                      style={{
                        padding: '1px 7px',
                        borderRadius: 'var(--radius-pill)',
                        fontSize: '10px',
                        fontWeight: 700,
                        backgroundColor: isActive ? 'rgba(255, 255, 255, 0.25)' : 'rgba(255, 255, 255, 0.08)',
                        color: isActive ? '#ffffff' : 'var(--text-muted)',
                      }}
                    >
                      {item.badge}
                    </span>
                  )}
                </button>
              </li>
            );
          })}
        </ul>
      </nav>

      {/* Backend Status Footer */}
      <div
        style={{
          padding: '16px 20px',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          fontSize: '12px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <div
            style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              backgroundColor: isBackendHealthy ? 'var(--color-success)' : 'var(--color-error)',
              boxShadow: isBackendHealthy
                ? '0 0 8px rgba(16, 185, 129, 0.6)'
                : '0 0 8px rgba(239, 68, 68, 0.6)',
            }}
          />
          <span style={{ color: 'var(--text-muted)' }}>
            {isBackendHealthy ? 'FastAPI Online' : 'Backend Offline'}
          </span>
        </div>
        <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>v6.2</span>
      </div>
    </aside>
  );
};
