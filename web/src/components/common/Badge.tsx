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

export const QualityBadge: React.FC<{
  quality?: number | string | null;
  isDownloaded?: boolean;
  className?: string;
  style?: React.CSSProperties;
}> = ({ quality, isDownloaded, className = '', style }) => {
  const numQuality = typeof quality === 'number' ? quality : parseInt(String(quality).replace(/\D/g, ''), 10) || 0;

  if (isDownloaded === false || (!quality && quality !== 0)) {
    const targetKbps = numQuality > 0 ? numQuality : 320;
    return (
      <span className={`quality-chip ${className}`} style={style}>
        {targetKbps} kbps · Target
      </span>
    );
  }

  let text = '320 kbps · High';
  if (numQuality >= 320) {
    text = '320 kbps · High';
  } else if (numQuality >= 192) {
    text = `${numQuality} kbps · Medium`;
  } else if (numQuality > 0) {
    text = `${numQuality} kbps · Standard`;
  } else {
    text = String(quality);
  }

  return (
    <span className={`quality-chip ${className}`} style={style}>
      {text}
    </span>
  );
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
          backgroundColor: 'rgba(212, 163, 89, 0.14)',
          color: '#E0B268',
          border: '1px solid rgba(212, 163, 89, 0.32)',
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
