/**
 * Audio Player Context: Native HTML5 Audio Streaming with Scrubbing, Volume, and Queue.
 */

import React, { createContext, useContext, useEffect, useRef, useState, useCallback } from 'react';
import { Song } from '../api/types';
import { api } from '../api/client';
import { useApp } from './AppContext';

interface AudioPlayerContextValue {
  currentSong: Song | null;
  isPlaying: boolean;
  isLoading: boolean;
  progress: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  queue: Song[];
  playSong: (song: Song, contextQueue?: Song[]) => void;
  togglePlay: () => void;
  seek: (seconds: number) => void;
  setVolume: (v: number) => void;
  toggleMute: () => void;
  addToQueue: (song: Song) => void;
  removeFromQueue: (index: number) => void;
  clearQueue: () => void;
  playNext: () => void;
  playPrevious: () => void;
}

const AudioPlayerContext = createContext<AudioPlayerContextValue | null>(null);

export const AudioPlayerProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { showToast } = useApp();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [currentSong, setCurrentSong] = useState<Song | null>(null);
  const currentSongRef = useRef<Song | null>(null);
  currentSongRef.current = currentSong;
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolumeState] = useState(0.85);
  const [isMuted, setIsMuted] = useState(false);
  const [queue, setQueue] = useState<Song[]>([]);
  const previousVolumeRef = useRef(0.85);

  // Initialize Audio element once
  useEffect(() => {
    const audio = new Audio();
    audioRef.current = audio;

    const handleTimeUpdate = () => {
      setProgress(audio.currentTime);
    };

    const handleLoadedMetadata = () => {
      setDuration(audio.duration || 0);
      setIsLoading(false);
    };

    const handleWaiting = () => {
      setIsLoading(true);
    };

    const handlePlaying = () => {
      setIsLoading(false);
      setIsPlaying(true);
    };

    const handlePause = () => {
      setIsPlaying(false);
    };

    const handleEnded = () => {
      setIsPlaying(false);
      playNext();
    };

    const handleError = () => {
      setIsLoading(false);
      setIsPlaying(false);
      setCurrentSong(null);
      currentSongRef.current = null;
      if (audioRef.current) {
        audioRef.current.removeAttribute('src');
        audioRef.current.load();
      }
      showToast(
        'Download the song before playing.',
        'warning',
        'Playback Unavailable'
      );
    };

    audio.addEventListener('timeupdate', handleTimeUpdate);
    audio.addEventListener('loadedmetadata', handleLoadedMetadata);
    audio.addEventListener('waiting', handleWaiting);
    audio.addEventListener('playing', handlePlaying);
    audio.addEventListener('pause', handlePause);
    audio.addEventListener('ended', handleEnded);
    audio.addEventListener('error', handleError);

    audio.volume = volume;

    return () => {
      audio.removeEventListener('timeupdate', handleTimeUpdate);
      audio.removeEventListener('loadedmetadata', handleLoadedMetadata);
      audio.removeEventListener('waiting', handleWaiting);
      audio.removeEventListener('playing', handlePlaying);
      audio.removeEventListener('pause', handlePause);
      audio.removeEventListener('ended', handleEnded);
      audio.removeEventListener('error', handleError);
      audio.pause();
    };
  }, [showToast]);

  const playSong = useCallback((song: Song, contextQueue?: Song[]) => {
    if (!audioRef.current) return;

    const isDownloaded = Boolean(
      song.has_file ||
      song.file_path ||
      (song.download_state && song.download_state.toUpperCase() === 'DOWNLOADED') ||
      (song as any).is_downloaded ||
      (song.state && song.state.toUpperCase() === 'OWNED')
    );

    if (!isDownloaded) {
      showToast(
        'Download the song before playing.',
        'warning',
        'Download Required'
      );
      return;
    }

    const audio = audioRef.current;
    setCurrentSong(song);
    currentSongRef.current = song;
    setIsLoading(true);
    setProgress(0);

    if (contextQueue && contextQueue.length > 0) {
      const idx = contextQueue.findIndex((s) => s.id === song.id);
      if (idx !== -1) {
        setQueue(contextQueue.slice(idx + 1));
      } else {
        setQueue(contextQueue);
      }
    }

    const streamUrl = api.getStreamUrl(song.id);
    audio.src = streamUrl;
    audio.load();

    audio.play().catch((err) => {
      console.warn('Autoplay prevented or stream error:', err);
      setIsLoading(false);
      setIsPlaying(false);
      setCurrentSong(null);
      currentSongRef.current = null;
      if (audioRef.current) {
        audioRef.current.removeAttribute('src');
        audioRef.current.load();
      }
      showToast(
        'Download the song before playing.',
        'warning',
        'Playback Unavailable'
      );
    });
  }, [showToast]);

  const togglePlay = useCallback(() => {
    if (!audioRef.current || !currentSong) return;
    const audio = audioRef.current;

    if (isPlaying) {
      audio.pause();
    } else {
      audio.play().catch(console.error);
    }
  }, [currentSong, isPlaying]);

  const seek = useCallback((seconds: number) => {
    if (!audioRef.current) return;
    audioRef.current.currentTime = Math.max(0, Math.min(seconds, duration));
    setProgress(audioRef.current.currentTime);
  }, [duration]);

  const setVolume = useCallback((v: number) => {
    const val = Math.max(0, Math.min(1, v));
    setVolumeState(val);
    if (audioRef.current) {
      audioRef.current.volume = val;
    }
    if (val > 0) {
      setIsMuted(false);
    }
  }, []);

  const toggleMute = useCallback(() => {
    if (!audioRef.current) return;
    if (isMuted) {
      setIsMuted(false);
      const restoreVol = previousVolumeRef.current || 0.85;
      setVolumeState(restoreVol);
      audioRef.current.volume = restoreVol;
    } else {
      previousVolumeRef.current = volume;
      setIsMuted(true);
      setVolumeState(0);
      audioRef.current.volume = 0;
    }
  }, [isMuted, volume]);

  const addToQueue = useCallback((song: Song) => {
    setQueue((prev) => [...prev, song]);
  }, []);

  const removeFromQueue = useCallback((index: number) => {
    setQueue((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const clearQueue = useCallback(() => {
    setQueue([]);
  }, []);

  const playNext = useCallback(() => {
    if (queue.length > 0) {
      const [nextSong, ...remaining] = queue;
      setQueue(remaining);
      playSong(nextSong);
    } else {
      setIsPlaying(false);
    }
  }, [queue, playSong]);

  const playPrevious = useCallback(() => {
    if (!audioRef.current) return;
    if (audioRef.current.currentTime > 3) {
      audioRef.current.currentTime = 0;
    }
  }, []);

  return (
    <AudioPlayerContext.Provider
      value={{
        currentSong,
        isPlaying,
        isLoading,
        progress,
        duration,
        volume,
        isMuted,
        queue,
        playSong,
        togglePlay,
        seek,
        setVolume,
        toggleMute,
        addToQueue,
        removeFromQueue,
        clearQueue,
        playNext,
        playPrevious,
      }}
    >
      {children}
    </AudioPlayerContext.Provider>
  );
};

export const useAudioPlayer = () => {
  const context = useContext(AudioPlayerContext);
  if (!context) {
    throw new Error('useAudioPlayer must be used within an AudioPlayerProvider');
  }
  return context;
};
