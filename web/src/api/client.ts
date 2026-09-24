/**
 * Universal Typed HTTP Client for FastAPI Backend.
 */

import { ApiResponse } from './types';

const BASE_URL = '/api';

export class ApiError extends Error {
  public status: number;
  public data?: any;

  constructor(message: string, status: number, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<ApiResponse<T>> {
  const url = `${BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
  
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    const isJson = response.headers.get('content-type')?.includes('application/json');
    const data = isJson ? await response.json() : null;

    if (!response.ok) {
      const errorMsg = data?.detail || data?.message || `Request failed with status ${response.status}`;
      throw new ApiError(errorMsg, response.status, data);
    }

    return data as ApiResponse<T>;
  } catch (err: any) {
    if (err instanceof ApiError) {
      throw err;
    }
    throw new ApiError(err?.message || 'Network request failed. Is the server running?', 0);
  }
}

export const api = {
  get: <T>(endpoint: string, params?: Record<string, any>) => {
    let query = '';
    if (params) {
      const cleanParams: Record<string, string> = {};
      Object.entries(params).forEach(([k, v]) => {
        if (v !== undefined && v !== null && v !== '') {
          cleanParams[k] = String(v);
        }
      });
      const qs = new URLSearchParams(cleanParams).toString();
      if (qs) query = `?${qs}`;
    }
    return request<T>(`${endpoint}${query}`, { method: 'GET' });
  },

  post: <T>(endpoint: string, body?: any) => {
    return request<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  put: <T>(endpoint: string, body?: any) => {
    return request<T>(endpoint, {
      method: 'PUT',
      body: body ? JSON.stringify(body) : undefined,
    });
  },

  delete: <T>(endpoint: string, params?: Record<string, any>) => {
    let query = '';
    if (params) {
      const qs = new URLSearchParams(params).toString();
      if (qs) query = `?${qs}`;
    }
    return request<T>(`${endpoint}${query}`, { method: 'DELETE' });
  },

  getArtworkUrl: (category: string, id: string | number, width = 300, height = 300) => {
    return `${BASE_URL}/artwork/${category}/${id}?width=${width}&height=${height}`;
  },

  getStreamUrl: (songId: number) => {
    return `${BASE_URL}/songs/${songId}/stream`;
  },
};
