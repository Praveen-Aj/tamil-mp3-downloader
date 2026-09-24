import React from 'react';
import { CheckCircle2, AlertCircle, Info, AlertTriangle, X } from 'lucide-react';
import { useApp } from '../../context/AppContext';

export const ToastContainer: React.FC = () => {
  const { toasts, removeToast } = useApp();

  if (toasts.length === 0) return null;

  return (
    <div
      style={{
        position: 'fixed',
        top: '20px',
        right: '24px',
        zIndex: 2000,
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
        maxWidth: '380px',
        width: '100%',
        pointerEvents: 'none',
      }}
    >
      {toasts.map((toast) => {
        let Icon = Info;
        let color = 'var(--color-info)';
        let bg = 'var(--bg-surface)';

        if (toast.type === 'success') {
          Icon = CheckCircle2;
          color = 'var(--color-success)';
        } else if (toast.type === 'error') {
          Icon = AlertCircle;
          color = 'var(--color-error)';
        } else if (toast.type === 'warning') {
          Icon = AlertTriangle;
          color = 'var(--color-warning)';
        }

        return (
          <div
            key={toast.id}
            className="glass-panel"
            style={{
              pointerEvents: 'auto',
              display: 'flex',
              alignItems: 'flex-start',
              gap: '12px',
              padding: '14px 16px',
              backgroundColor: bg,
              boxShadow: 'var(--shadow-lg)',
              borderLeft: `4px solid ${color}`,
              borderRadius: 'var(--radius-md)',
              animation: 'slide-in-right 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
            }}
          >
            <Icon size={20} color={color} style={{ flexShrink: 0, marginTop: '2px' }} />
            <div style={{ flex: 1 }}>
              {toast.title && (
                <div style={{ fontWeight: 600, fontSize: '13px', color: 'var(--text-primary)' }}>
                  {toast.title}
                </div>
              )}
              <div style={{ fontSize: '12px', color: 'var(--text-secondary)', lineHeight: 1.4 }}>
                {toast.message}
              </div>
            </div>
            <button
              onClick={() => removeToast(toast.id)}
              style={{
                color: 'var(--text-muted)',
                cursor: 'pointer',
                padding: '2px',
                marginTop: '1px',
              }}
            >
              <X size={14} />
            </button>
          </div>
        );
      })}
    </div>
  );
};
