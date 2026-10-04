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
  Radio,
  X,
  MoreHorizontal,
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
        { id: 'dashboard', label: 'Home', icon: <LayoutDashboard size={18} /> },
        { id: 'charts', label: 'Top Charts', icon: <Flame size={18} /> },
        { id: 'movies', label: 'Movies', icon: <Film size={18} />, badge: stats?.total_movies },
        { id: 'artists', label: 'Artists', icon: <Users size={18} />, badge: stats?.total_artists },
      ],
    },
    {
      title: 'My Collection',
      items: [
        { id: 'songs', label: 'Songs', icon: <Music size={18} />, badge: stats?.total_songs },
        { id: 'playlists', label: 'Playlists', icon: <ListMusic size={18} />, badge: stats?.total_playlists },
        { id: 'favorites', label: 'Favorites', icon: <Heart size={18} /> },
        {
          id: 'downloads',
          label: 'Downloads',
          icon: <ArrowDownCircle size={18} />,
          badge: stats?.active_downloads ? stats.active_downloads : undefined,
        },
      ],
    },
    {
      title: 'Tools',
      items: [
        { id: 'imports', label: 'Import', icon: <Link2 size={18} /> },
        { id: 'settings', label: 'Settings', icon: <Settings size={18} /> },
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
    onClose(); // close on mobile after navigation
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
        {/* Brand Header */}
        <div
          style={{
            padding: '20px 20px 16px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            borderBottom: '1px solid var(--border-subtle)',
          }}
        >
          <button
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '10px',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: 0,
            }}
            onClick={() => handleNavClick('dashboard')}
            aria-label="Go to home"
          >
            <div
              style={{
                width: '34px',
                height: '34px',
                borderRadius: '9px',
                background: 'linear-gradient(135deg, #9C8FFD 0%, #7A6BE8 100%)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                /* No box-shadow glow */
              }}
            >
              <Radio size={18} color="#ffffff" />
            </div>
            <div
              className="title-display"
              style={{ fontSize: '15px', fontWeight: 800, lineHeight: 1.1, color: 'var(--text-primary)' }}
            >
              TAMIL MP3
            </div>
          </button>

          {/* Close button — visible on mobile */}
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
            padding: '12px 12px',
            flex: 1,
            overflowY: 'auto',
            display: 'flex',
            flexDirection: 'column',
            gap: '18px',
          }}
        >
          {sections.map((section) => (
            <div key={section.title}>
              <div
                style={{
                  fontSize: '10px',
                  fontWeight: 700,
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                  color: 'var(--text-muted)',
                  padding: '0 10px 5px',
                }}
              >
                {section.title}
              </div>
              <ul style={{ display: 'flex', flexDirection: 'column', gap: '2px', margin: 0, padding: 0, listStyle: 'none' }}>
                {section.items.map((item) => {
                  const isActive = currentView === item.id ||
                    (currentView === 'movie_detail' && item.id === 'movies') ||
                    (currentView === 'artist_detail' && item.id === 'artists');
                  return (
                    <li key={item.id}>
                      <button
                        onClick={() => handleNavClick(item.id)}
                        className={`sidebar-nav-item ${isActive ? 'active' : ''}`}
                        aria-current={isActive ? 'page' : undefined}
                      >
                        <div style={{ display: 'flex', alignItems: 'center', gap: '9px' }}>
                          {item.icon}
                          <span>{item.label}</span>
                        </div>
                        {item.badge !== undefined && item.badge > 0 && (
                          <span
                            style={{
                              padding: '1px 6px',
                              borderRadius: 'var(--radius-pill)',
                              fontSize: '10.5px',
                              fontWeight: 700,
                              fontVariantNumeric: 'tabular-nums',
                              backgroundColor: isActive ? 'rgba(139, 124, 248, 0.22)' : 'rgba(255, 255, 255, 0.07)',
                              color: isActive ? 'var(--primary-light)' : 'var(--text-muted)',
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
      </aside>

      {/* Mobile Bottom Navigation Bar — 4 primary destinations */}
      <nav className="mobile-nav-bar" aria-label="Main navigation">
        {[
          { id: 'dashboard' as ViewType, label: 'Home', icon: <LayoutDashboard size={20} /> },
          { id: 'movies' as ViewType, label: 'Movies', icon: <Film size={20} /> },
          { id: 'songs' as ViewType, label: 'Library', icon: <Music size={20} /> },
          { id: 'downloads' as ViewType, label: 'Downloads', icon: <ArrowDownCircle size={20} /> },
          { id: 'settings' as ViewType, label: 'More', icon: <MoreHorizontal size={20} />, openSidebar: true },
        ].map((item: any) => {
          const isActive = currentView === item.id ||
            (item.id === 'movies' && currentView === 'movie_detail') ||
            (item.id === 'songs' && currentView === 'artist_detail');
          return (
            <button
              key={item.id}
              className={`mobile-nav-item${isActive ? ' active' : ''}`}
              onClick={() => {
                if (item.openSidebar) {
                  onClose(); // toggle — handled by parent
                  // We want to open, not close, so we call a different handler:
                  // The parent manages sidebarOpen state
                  // We trigger via a custom event
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
