/**
 * Global App Context: Navigation, Views, System Health, and Toast Notifications.
 */

import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import { systemApi } from '../api/endpoints';
import { SystemStats } from '../api/types';

export type ViewType =
  | 'dashboard'
  | 'songs'
  | 'movies'
  | 'artists'
  | 'charts'
  | 'playlists'
  | 'downloads'
  | 'imports'
  | 'settings'
  | 'movie_detail'
  | 'artist_detail';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info' | 'warning';
  title?: string;
  message: string;
}

interface AppContextValue {
  currentView: ViewType;
  selectedEntityId: number | string | null;
  navigateTo: (view: ViewType, entityId?: number | string | null) => void;
  stats: SystemStats | null;
  refreshStats: () => Promise<void>;
  toasts: ToastMessage[];
  showToast: (message: string, type?: ToastMessage['type'], title?: string) => void;
  removeToast: (id: string) => void;
  globalSearchQuery: string;
  setGlobalSearchQuery: (q: string) => void;
  isBackendHealthy: boolean;
}

const AppContext = createContext<AppContextValue | null>(null);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentView, setCurrentView] = useState<ViewType>('dashboard');
  const [selectedEntityId, setSelectedEntityId] = useState<number | string | null>(null);
  const [stats, setStats] = useState<SystemStats | null>(null);
  const [isBackendHealthy, setIsBackendHealthy] = useState(true);
  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [globalSearchQuery, setGlobalSearchQuery] = useState('');

  const navigateTo = useCallback((view: ViewType, entityId: number | string | null = null) => {
    setCurrentView(view);
    setSelectedEntityId(entityId);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, []);

  const showToast = useCallback((message: string, type: ToastMessage['type'] = 'info', title?: string) => {
    const id = Math.random().toString(36).substring(2, 9);
    setToasts((prev) => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  }, []);

  const removeToast = useCallback((id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const refreshStats = useCallback(async () => {
    try {
      const res = await systemApi.getStats();
      if (res.success && res.data) {
        setStats(res.data);
        setIsBackendHealthy(true);
      }
    } catch (err) {
      setIsBackendHealthy(false);
    }
  }, []);

  useEffect(() => {
    refreshStats();
    const interval = setInterval(refreshStats, 8000);
    return () => clearInterval(interval);
  }, [refreshStats]);

  return (
    <AppContext.Provider
      value={{
        currentView,
        selectedEntityId,
        navigateTo,
        stats,
        refreshStats,
        toasts,
        showToast,
        removeToast,
        globalSearchQuery,
        setGlobalSearchQuery,
        isBackendHealthy,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
