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

export const QualityBadge: React.FC<{ quality?: number | null }> = ({ quality }) => {
  if (!quality) return <Badge variant="subtle">Standard</Badge>;
  if (quality >= 320) return <Badge variant="success">320 KBPS</Badge>;
  if (quality >= 192) return <Badge variant="primary">{quality} KBPS</Badge>;
  return <Badge variant="warning">{quality} KBPS</Badge>;
};

export const StateBadge: React.FC<{ state?: string }> = ({ state = 'NEW' }) => {
  switch (state.toUpperCase()) {
    case 'OWNED':
      return <Badge variant="success">Downloaded</Badge>;
    case 'NEW':
      return <Badge variant="primary">Available</Badge>;
    case 'DOWNLOADING':
      return <Badge variant="warning">Downloading</Badge>;
    case 'FAILED':
      return <Badge variant="error">Failed</Badge>;
    default:
      return <Badge variant="subtle">{state}</Badge>;
  }
};
