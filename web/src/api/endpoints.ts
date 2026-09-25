/**
 * Concrete domain API service endpoints for Tamil MP3 Downloader.
 */

import { api } from './client';
import {
  Artist,
  Chart,
  ChartEntry,
  DownloadPlanResult,
  DownloadTask,
  ImportJob,
  Movie,
  PaginatedResponse,
  Playlist,
  RegisteredSource,
  Song,
  SystemStats,
} from './types';

export const systemApi = {
  getHealth: () => api.get<{ status: string; version: string }>('/system/health'),
  getStats: () => api.get<SystemStats>('/system/stats'),
  getSources: () => api.get<{ sources: RegisteredSource[] }>('/system/sources'),
};

export const songsApi = {
  getSongs: (params?: {
    query?: string;
    state?: string;
    year?: number;
    source?: string;
    quality?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  }) => api.get<PaginatedResponse<Song>>('/songs', params),

  getDownloadedSongs: (params?: { query?: string; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Song>>('/songs/downloaded', params),

  getFavorites: (params?: { query?: string; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Song>>('/songs/favorites', params),

  getSong: (songId: number) =>
    api.get<{ song: Song; sources: any[]; contexts: any[]; planner_decision: any }>(`/songs/${songId}`),

  rateSong: (songId: number, rating: number | null) =>
    api.post<{ song_id: number; rating: number | null }>(`/songs/${songId}/rating`, { rating }),

  toggleFavorite: (songId: number, isFavorite?: boolean) =>
    api.post<{ song_id: number; is_favorite: boolean }>(`/songs/${songId}/favorite`, {
      is_favorite: isFavorite,
    }),

  openFolder: (songId: number) => api.post(`/songs/${songId}/open-folder`),

  deleteSong: (songId: number, deletePhysicalFile = false, removeFromLibrary = true) =>
    api.delete(`/songs/${songId}`, {
      delete_physical_file: String(deletePhysicalFile),
      remove_from_library: String(removeFromLibrary),
    }),

  downloadMissingSongs: (preferredQuality = 320) =>
    api.post<{ queued_count: number }>(`/songs/download-missing?preferred_quality=${preferredQuality}`),
};

export const moviesApi = {
  getMovies: (params?: {
    query?: string;
    min_year?: number;
    max_year?: number;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  }) => api.get<PaginatedResponse<Movie>>('/movies', params),

  getMovie: (movieId: number) => api.get<Movie>(`/movies/${movieId}`),

  getMovieSongs: (movieId: number) =>
    api.get<{ movie: Movie; songs: Song[]; stats: any }>(`/movies/${movieId}/songs`),

  planDownload: (movieId: number, preferredQuality = 320) =>
    api.post<DownloadPlanResult>(`/movies/${movieId}/plan`, { preferred_quality: preferredQuality }),

  startDownload: (movieId: number, preferredQuality = 320) =>
    api.post<{ queued_count: number; movie_id: number }>(`/movies/${movieId}/download`, {
      preferred_quality: preferredQuality,
    }),
};

export const artistsApi = {
  getArtists: (params?: {
    query?: string;
    role?: string;
    sort_by?: string;
    sort_order?: 'asc' | 'desc';
    page?: number;
    page_size?: number;
  }) => api.get<PaginatedResponse<Artist>>('/artists', params),

  getArtist: (artistId: number) => api.get<Artist>(`/artists/${artistId}`),

  getArtistSongs: (artistId: number) =>
    api.get<{ artist: Artist; songs: Song[]; soundtracks: any[] }>(`/artists/${artistId}/songs`),

  planDownload: (artistId: number, preferredQuality = 320) =>
    api.post<DownloadPlanResult>(`/artists/${artistId}/plan`, { preferred_quality: preferredQuality }),

  startDownload: (artistId: number, preferredQuality = 320) =>
    api.post<{ queued_count: number; artist_id: number }>(`/artists/${artistId}/download`, {
      preferred_quality: preferredQuality,
    }),
};

export const chartsApi = {
  getCharts: () => api.get<{ charts: Chart[] }>('/charts'),

  getChart: (chartId: string) =>
    api.get<{ chart: Chart; entries: ChartEntry[]; total: number }>(`/charts/${chartId}`),

  refreshChart: (chartId: string) => api.post(`/charts/${chartId}/refresh`),

  planDownload: (chartId: string, preferredQuality = 320) =>
    api.post<DownloadPlanResult>(`/charts/${chartId}/plan`, { preferred_quality: preferredQuality }),

  startDownload: (chartId: string, preferredQuality = 320) =>
    api.post<{ queued_count: number; chart_id: string }>(`/charts/${chartId}/download`, {
      preferred_quality: preferredQuality,
    }),
};

export const playlistsApi = {
  getPlaylists: (params?: { query?: string; page?: number; page_size?: number }) =>
    api.get<PaginatedResponse<Playlist>>('/playlists', params),

  createPlaylist: (name: string, description = '') =>
    api.post<Playlist>('/playlists', { name, description }),

  getPlaylist: (playlistId: number) =>
    api.get<{ playlist: Playlist; songs: Song[]; total: number }>(`/playlists/${playlistId}`),

  addSong: (playlistId: number, songId: number) =>
    api.post(`/playlists/${playlistId}/add-song`, { song_id: songId }),

  removeSong: (playlistId: number, songId: number) =>
    api.post(`/playlists/${playlistId}/remove-song`, { song_id: songId }),

  deletePlaylist: (playlistId: number) => api.delete(`/playlists/${playlistId}`),

  planDownload: (playlistId: number, preferredQuality = 320) =>
    api.post<DownloadPlanResult>(`/playlists/${playlistId}/plan`, { preferred_quality: preferredQuality }),

  startDownload: (playlistId: number, preferredQuality = 320) =>
    api.post<{ queued_count: number; playlist_id: number }>(`/playlists/${playlistId}/download`, {
      preferred_quality: preferredQuality,
    }),
};

export const searchApi = {
  searchGlobal: (query: string, limit = 8) =>
    api.get<{
      query: string;
      songs: Song[];
      movies: Movie[];
      artists: Artist[];
      playlists: Playlist[];
      charts: Chart[];
    }>('/search/global', { q: query, limit }),
};

export const downloadsApi = {
  getDownloads: () => api.get<{ active: DownloadTask[]; queue: DownloadTask[]; history: DownloadTask[] }>('/downloads'),
  getActiveDownloads: () => api.get<{ active: DownloadTask[] }>('/downloads/active'),
  getHistory: (limit = 50) => api.get<{ history: DownloadTask[] }>('/downloads/history', { limit }),

  planSongs: (songIds: number[], preferredQuality = 320) =>
    api.post<DownloadPlanResult>('/downloads/plan', { song_ids: songIds, preferred_quality: preferredQuality }),

  queueSongs: (songIds: number[], preferredQuality = 320) =>
    api.post<{ queued_count: number; plan: DownloadPlanResult }>('/downloads/queue', {
      song_ids: songIds,
      preferred_quality: preferredQuality,
    }),

  cancelTask: (taskId: number) => api.post(`/downloads/${taskId}/cancel`),
  retryTask: (taskId: number) => api.post(`/downloads/${taskId}/retry`),
};

export const importsApi = {
  startUrlImport: (url: string) => api.post<ImportJob>('/imports/url', { url }),
  getJobStatus: (jobId: string) => api.get<ImportJob>(`/imports/jobs/${jobId}`),
};

export const settingsApi = {
  getSettings: () => api.get<Record<string, any>>('/settings'),
  updateSettings: (newSettings: Record<string, any>) => api.post('/settings', newSettings),
  validatePath: (path: string) => api.post<{ is_valid: boolean; message: string; resolved_path?: string }>('/settings/validate-path', { path }),
};
