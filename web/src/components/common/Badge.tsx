import React from 'react';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'primary' | 'success' | 'warning' | 'error' | 'subtle';
  className?: string;
  style?: React.CSSProperties;
}

export const Badge: React.FC<BadgeProps> = ({ children, variant = 'subtle', className = '', style }) => {
  return (
    <span className={`badge badge-${variant} ${className}`} style={style}>
      {children}
    </span>
  );
};

export const QualityBadge: React.FC<{ quality?: number | null; isDownloaded?: boolean }> = ({ quality, isDownloaded }) => {
  if (isDownloaded === false || !quality) return <Badge variant="subtle">Target 320 kbps</Badge>;
  if (quality >= 320) return <Badge variant="success">320 kbps • High Quality</Badge>;
  if (quality >= 192) return <Badge variant="primary">{quality} kbps</Badge>;
  return <Badge variant="subtle">{quality} kbps • Standard</Badge>;
};

export const StateBadge: React.FC<{
  state?: string;
  downloadState?: string;
  canUpgrade?: boolean;
}> = ({ state = 'NEW', downloadState, canUpgrade }) => {
  const effectiveState = (downloadState || state).toUpperCase();

  if (canUpgrade || effectiveState === 'UPGRADE_AVAILABLE') {
    return (
      <Badge
        variant="warning"
        style={{
          backgroundColor: 'rgba(245, 158, 11, 0.15)',
          color: '#fbbf24',
          border: '1px solid rgba(245, 158, 11, 0.3)',
          fontWeight: 600,
        }}
      >
        Upgrade Available
      </Badge>
    );
  }

  switch (effectiveState) {
    case 'OWNED':
    case 'DOWNLOADED':
      return <Badge variant="success">Downloaded</Badge>;
    case 'DOWNLOADING':
      return <Badge variant="warning">Downloading</Badge>;
    case 'FAILED':
      return <Badge variant="error">Failed</Badge>;
    case 'NEW':
    case 'NOT_DOWNLOADED':
    default:
      return (
        <Badge variant="subtle" style={{ color: 'var(--text-muted)', border: '1px solid var(--border-subtle)' }}>
          Not Downloaded
        </Badge>
      );
  }
};

export const DownloadStateBadge = StateBadge;
