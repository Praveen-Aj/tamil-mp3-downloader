/**
 * TypeScript Data Models for Tamil MP3 Downloader Web Application.
 * Matches backend schemas in api/schemas/*.py
 */

export interface ApiResponse<T = any> {
  success: boolean;
  message: string;
  data: T;
  error?: string | null;
}

export interface PaginatedResponse<T = any> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface Song {
  id: number;
  canonical_hash?: string;
  title: string;
  artist?: string;
  album?: string;
  year?: number;
  state: 'NEW' | 'OWNED' | 'FAILED' | 'ARCHIVED' | string;
  rating?: number | null;
  is_favorite: boolean;
  has_file: boolean;
  file_path?: string | null;
  quality?: number | null;
  sources_count?: number;
  duration_sec?: number;
}

export interface Movie {
  id: number;
  title: string;
  name?: string;
  year?: number;
  director?: string;
  music_director?: string;
  poster_url?: string;
  total_songs?: number;
  downloaded_count?: number;
}

export interface Artist {
  id: number;
  name: string;
  role?: string;
  image_url?: string;
  photo_url?: string;
  total_tracks?: number;
  downloaded_tracks?: number;
  total_soundtracks?: number;
}

export interface Chart {
  id: string;
  title: string;
  chart_type: string;
  provider_name: string;
  snapshot_date?: string;
  total_entries?: number;
  frequency?: string;
}

export interface ChartEntry {
  chart_id: string;
  rank: number;
  song_id?: number | null;
  raw_title: string;
  is_owned?: boolean;
}

export interface Playlist {
  id: number;
  name: string;
  description: string;
  song_count?: number;
  created_at?: string;
}

export interface DownloadTask {
  id: number;
  song_id: number;
  title: string;
  artist?: string;
  album?: string;
  status: 'pending' | 'downloading' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  speed_bytes_sec?: number;
  speed_str?: string;
  eta_sec?: number;
  eta_str?: string;
  quality: number;
  source_name: string;
  error?: string;
}

export interface SystemStats {
  total_songs: number;
  total_owned: number;
  total_movies: number;
  total_artists: number;
  total_charts: number;
  total_playlists: number;
  active_downloads: number;
  queued_downloads: number;
  total_storage_bytes?: number;
  healthy_sources?: number;
  upgrades_available?: number;
}

export interface RegisteredSource {
  name: string;
  display_name: string;
  enabled: boolean;
  priority: number;
  is_usable: boolean;
}

export interface DownloadPlanResult {
  new_songs_count: number;
  owned_count: number;
  upgrades_count: number;
  total_items: number;
  items: Array<{
    song_id: number;
    title: string;
    artist?: string;
    source_name?: string;
    quality_kbps?: number;
    action: string;
  }>;
}

export interface ImportJob {
  id: string;
  url: string;
  platform: 'spotify' | 'youtube' | 'direct' | 'unknown';
  status: 'analyzing' | 'matching' | 'ready' | 'downloading' | 'completed' | 'failed';
  total_tracks: number;
  matched_tracks: number;
  downloaded_tracks: number;
  error?: string;
}
