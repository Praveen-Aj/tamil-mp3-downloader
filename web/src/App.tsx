import React from 'react';
import { AppProvider, useApp } from './context/AppContext';
import { AudioPlayerProvider } from './context/AudioPlayerContext';
import { WebSocketProvider } from './context/WebSocketContext';
import { Sidebar } from './components/layout/Sidebar';
import { Header } from './components/layout/Header';
import { PlayerBar } from './components/layout/PlayerBar';
import { ToastContainer } from './components/common/Toast';

import { DashboardView } from './components/views/DashboardView';
import { SongsView } from './components/views/SongsView';
import { MoviesView } from './components/views/MoviesView';
import { ArtistsView } from './components/views/ArtistsView';
import { ChartsView } from './components/views/ChartsView';
import { PlaylistsView } from './components/views/PlaylistsView';
import { FavoritesView } from './components/views/FavoritesView';
import { SearchView } from './components/views/SearchView';
import { DownloadsView } from './components/views/DownloadsView';
import { ImportsView } from './components/views/ImportsView';
import { SettingsView } from './components/views/SettingsView';
import { MovieDetailView } from './components/views/MovieDetailView';
import { ArtistDetailView } from './components/views/ArtistDetailView';

const MainContent: React.FC = () => {
  const { currentView } = useApp();

  const renderView = () => {
    switch (currentView) {
      case 'dashboard':
        return <DashboardView />;
      case 'songs':
        return <SongsView />;
      case 'movies':
        return <MoviesView />;
      case 'artists':
        return <ArtistsView />;
      case 'charts':
        return <ChartsView />;
      case 'playlists':
        return <PlaylistsView />;
      case 'favorites':
        return <FavoritesView />;
      case 'search':
        return <SearchView />;
      case 'downloads':
        return <DownloadsView />;
      case 'imports':
        return <ImportsView />;
      case 'settings':
        return <SettingsView />;
      case 'movie_detail':
        return <MovieDetailView />;
      case 'artist_detail':
        return <ArtistDetailView />;
      default:
        return <DashboardView />;
    }
  };

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        height: '100%',
        width: '100%',
        overflow: 'hidden',
        backgroundColor: 'var(--bg-app)',
      }}
    >
      <div style={{ display: 'flex', flex: 1, height: 'calc(100% - var(--player-height))', overflow: 'hidden' }}>
        <Sidebar />
        <div style={{ display: 'flex', flexDirection: 'column', flex: 1, minWidth: 0, overflow: 'hidden' }}>
          <Header />
          <main style={{ flex: 1, overflowY: 'auto', paddingBottom: '96px' }}>
            {renderView()}
          </main>
        </div>
      </div>

      <PlayerBar />
      <ToastContainer />
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <AppProvider>
      <AudioPlayerProvider>
        <WebSocketProvider>
          <MainContent />
        </WebSocketProvider>
      </AudioPlayerProvider>
    </AppProvider>
  );
};

export default App;
