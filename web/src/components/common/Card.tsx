import React from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
  onClick?: (e: React.MouseEvent<HTMLDivElement>) => void;
  hoverable?: boolean;
  style?: React.CSSProperties;
}

export const Card: React.FC<CardProps> = ({
  children,
  className = '',
  onClick,
  hoverable = true,
  style = {},
  ...rest
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
      {...rest}
    >
      {children}
    </div>
  );
};

