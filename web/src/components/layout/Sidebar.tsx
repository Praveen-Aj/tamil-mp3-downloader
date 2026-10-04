import React, { useEffect } from 'react';
import {
  LayoutDashboard,
  Music,
  Film,
  Users,
  Flame,
  ListMusic,
  Heart,
  ArrowDownCircle,
  Link2,
  Settings,
  Disc3,
  X,
  MoreHorizontal,
  HardDrive,
  CheckCircle2,
} from 'lucide-react';
import { useApp, ViewType } from '../../context/AppContext';

interface NavItem {
  id: ViewType;
  label: string;
  icon: React.ReactNode;
  badge?: number;
}

interface NavSection {
  title: string;
  items: NavItem[];
}

interface SidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { currentView, navigateTo, stats } = useApp();

  const sections: NavSection[] = [
    {
      title: 'Discover',
      items: [
        { id: 'dashboard', label: 'Home', icon: <LayoutDashboard size={17} /> },
        { id: 'charts', label: 'Top Charts', icon: <Flame size={17} /> },
        { id: 'movies', label: 'Soundtracks', icon: <Film size={17} />, badge: stats?.total_movies },
        { id: 'artists', label: 'Artists', icon: <Users size={17} />, badge: stats?.total_artists },
      ],
    },
    {
      title: 'Library',
      items: [
        { id: 'songs', label: 'All Tracks', icon: <Music size={17} />, badge: stats?.total_songs },
        { id: 'playlists', label: 'Playlists', icon: <ListMusic size={17} />, badge: stats?.total_playlists },
        { id: 'favorites', label: 'Favorites', icon: <Heart size={17} /> },
        {
          id: 'downloads',
          label: 'Downloads',
          icon: <ArrowDownCircle size={17} />,
          badge: stats?.active_downloads ? stats.active_downloads : undefined,
        },
      ],
    },
    {
      title: 'System',
      items: [
        { id: 'imports', label: 'Import URLs', icon: <Link2 size={17} /> },
        { id: 'settings', label: 'Preferences', icon: <Settings size={17} /> },
      ],
    },
  ];

  // Close sidebar on ESC key
  useEffect(() => {
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) onClose();
    };
    document.addEventListener('keydown', handleKey);
    return () => document.removeEventListener('keydown', handleKey);
  }, [isOpen, onClose]);

  const handleNavClick = (id: ViewType) => {
    navigateTo(id);
    onClose();
  };

  const formatStorage = (bytes?: number) => {
    if (!bytes) return '0 MB';
    const mb = bytes / (1024 * 1024);
    if (mb > 1024) return `${(mb / 1024).toFixed(1)} GB`;
    return `${Math.round(mb)} MB`;
  };

  return (
    <>
      {/* Sidebar backdrop (mobile only) */}
      {isOpen && (
        <div
          className="sidebar-backdrop open"
          onClick={onClose}
          aria-label="Close menu"
        />
      )}

      <aside className={`sidebar-container${isOpen ? ' open' : ''}`}>
        {/* Brand Header - Machined Audio Soundmark */}
        <div
          style={{
            padding: '22px 18px 18px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-sidebar)',
          }}
        >
          <button
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '12px',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
              textAlign: 'left',
            }}
            onClick={() => handleNavClick('dashboard')}
            aria-label="Go to home"
          >
            {/* Double-bezel soundmark logo */}
            <div
              style={{
                width: '36px',
                height: '36px',
                borderRadius: 'var(--radius-md)',
                background: 'linear-gradient(135deg, #E0B268 0%, #C59B4B 100%)',
                boxShadow: '0 2px 10px rgba(212, 163, 89, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.25)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              <Disc3 size={20} color="#07080A" strokeWidth={2.2} />
            </div>
            <div>
              <div
                className="title-display"
                style={{
                  fontSize: '15px',
                  fontWeight: 800,
                  letterSpacing: '0.04em',
                  lineHeight: 1.1,
                  color: 'var(--text-primary)',
                }}
              >
                TAMIL MP3
              </div>
              <div
                style={{
                  fontSize: '9.5px',
                  fontWeight: 700,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                  color: 'var(--accent-primary)',
                  marginTop: '2px',
                }}
              >
                HI-FI CONSOLE
              </div>
            </div>
          </button>

          {/* Close button (mobile only) */}
          <button
            className="btn-icon header-hamburger"
            onClick={onClose}
            aria-label="Close sidebar"
            style={{ width: '32px', height: '32px' }}
          >
            <X size={18} />
          </button>
        </div>

        {/* Grouped Navigation Sections */}
        <nav
          style={{
            padding: '16px 10px',
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '20px',
          }}
        >
          {sections.map((section) => (
            <div key={section.title}>
              <div
                style={{
                  fontSize: '9.5px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.12em',
                  color: 'var(--text-muted)',
                  padding: '0 12px 6px',
                }}
              >
                {section.title}
              </div>
              <ul style={{ display: 'flex', flexDirection: 'column', gap: '3px', margin: 0, padding: 0, listStyle: 'none' }}>
                {section.items.map((item) => {
                  const isActive =
                    currentView === item.id ||
                    (currentView === 'movie_detail' && item.id === 'movies') ||
                    (currentView === 'artist_detail' && item.id === 'artists');
                  return (
                    <li key={item.id}>
                      <button
                        onClick={() => handleNavClick(item.id)}
                        className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
                        aria-current={isActive ? 'page' : undefined}
                        style={{
                          borderLeft: isActive ? '3px solid var(--accent-primary)' : '3px solid transparent',
                          borderRadius: 'var(--radius-sm)',
                        }}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                          <span style={{ color: isActive ? 'var(--accent-primary)' : 'inherit', display: 'flex', alignItems: 'center' }}>
                            {item.icon}
                          </span>
                          <span style={{ fontWeight: isActive ? 600 : 500 }}>{item.label}</span>
                        </div>
                        {item.badge !== undefined && item.badge > 0 && (
                          <span
                            style={{
                              padding: '1.5px 7px',
                              borderRadius: 'var(--radius-pill)',
                              fontSize: '10.5px',
                              fontWeight: 700,
                              fontVariantNumeric: 'tabular-nums',
                              backgroundColor: isActive ? 'rgba(212, 163, 89, 0.16)' : 'rgba(255, 255, 255, 0.05)',
                              color: isActive ? '#E0B268' : 'var(--text-muted)',
                              border: isActive ? '1px solid rgba(212, 163, 89, 0.35)' : '1px solid transparent',
                            }}
                          >
                            {item.badge > 9999 ? `${Math.round(item.badge / 1000)}k` : item.badge}
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* Anchored Hardware Status Deck */}
        <div
          style={{
            padding: '14px 14px 18px',
            borderTop: '1px solid var(--border-subtle)',
            backgroundColor: 'var(--bg-inset)',
          }}
        >
          <div
            style={{
              padding: '10px 12px',
              borderRadius: 'var(--radius-md)',
              backgroundColor: 'var(--bg-surface)',
              border: '1px solid var(--border-subtle)',
              display: 'flex',
              flexDirection: 'column',
              gap: '6px',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
              <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <CheckCircle2 size={12} color="var(--color-success)" />
                <span>Ready</span>
              </span>
              <span style={{ color: 'var(--text-primary)', fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>
                {stats?.total_owned ?? 0} tracks
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '11px' }}>
              <span style={{ color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '5px' }}>
                <HardDrive size={12} color="var(--accent-primary)" />
                <span>Storage</span>
              </span>
              <span style={{ color: 'var(--text-secondary)', fontWeight: 500, fontVariantNumeric: 'tabular-nums' }}>
                {formatStorage(stats?.total_storage_bytes)}
              </span>
            </div>
          </div>
        </div>
      </aside>

      {/* Mobile Bottom Navigation Bar */}
      <nav className="mobile-nav-bar" aria-label="Main navigation">
        {[
          { id: 'dashboard' as ViewType, label: 'Home', icon: <LayoutDashboard size={20} /> },
          { id: 'movies' as ViewType, label: 'Movies', icon: <Film size={20} /> },
          { id: 'songs' as ViewType, label: 'Tracks', icon: <Music size={20} /> },
          { id: 'downloads' as ViewType, label: 'Queue', icon: <ArrowDownCircle size={20} /> },
          { id: 'settings' as ViewType, label: 'More', icon: <MoreHorizontal size={20} />, openSidebar: true },
        ].map((item: any) => {
          const isActive =
            currentView === item.id ||
            (item.id === 'movies' && currentView === 'movie_detail') ||
            (item.id === 'songs' && currentView === 'artist_detail');
          return (
            <button
              key={item.id}
              className={`mobile-nav-item${isActive ? ' active' : ''}`}
              onClick={() => {
                if (item.openSidebar) {
                  onClose();
                  document.dispatchEvent(new CustomEvent('open-sidebar'));
                } else {
                  navigateTo(item.id as ViewType);
                }
              }}
              aria-label={item.label}
              aria-current={isActive ? 'page' : undefined}
            >
              {item.icon}
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>
    </>
  );
};
