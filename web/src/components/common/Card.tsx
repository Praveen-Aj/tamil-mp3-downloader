import React from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  onClick?: () => void;
  hoverable?: boolean;
  style?: React.CSSProperties;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  onClick,
  hoverable = true,
  style = {},
}) => {
  return (
    <div
      onClick={onClick}
      className={`${hoverable ? 'glass-card' : 'glass-panel'} ${className}`}
      style={{
        cursor: onClick ? 'pointer' : 'default',
        padding: '16px',
        position: 'relative',
        overflow: 'hidden',
        ...style,
      }}
    >
      {children}
    </div>
  );
};
