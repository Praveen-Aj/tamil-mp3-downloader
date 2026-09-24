import React, { useState } from 'react';
import {
  Play,
  Pause,
  SkipBack,
  SkipForward,
  Volume2,
  VolumeX,
  Heart,
  Music,
  Loader2,
} from 'lucide-react';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { api } from '../../api/client';
import { QualityBadge } from '../common/Badge';
import { songsApi } from '../../api/endpoints';

export const PlayerBar: React.FC = () => {
  const {
    currentSong,
    isPlaying,
    isLoading,
    progress,
    duration,
    volume,
    isMuted,
    togglePlay,
    seek,
    setVolume,
    toggleMute,
    playNext,
    playPrevious,
  } = useAudioPlayer();

  const [isFav, setIsFav] = useState(false);

  // Sync favorite state
  React.useEffect(() => {
    if (currentSong) {
      setIsFav(currentSong.is_favorite);
    }
  }, [currentSong]);

  const handleToggleFavorite = async () => {
    if (!currentSong) return;
    try {
      const nextFav = !isFav;
      setIsFav(nextFav);
      await songsApi.toggleFavorite(currentSong.id, nextFav);
    } catch (err) {
      console.error('Failed to toggle favorite:', err);
    }
  };

  const formatTime = (seconds: number) => {
    if (!seconds || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  if (!currentSong) {
    return (
      <footer
        style={{
          height: 'var(--player-height)',
          backgroundColor: 'var(--bg-player)',
          backdropFilter: 'blur(20px)',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          fontSize: '13px',
          userSelect: 'none',
          padding: '0 24px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Music size={16} />
          <span>Select any track to play high-fidelity audio stream</span>
        </div>
      </footer>
    );
  }

  const progressPercent = duration > 0 ? (progress / duration) * 100 : 0;

  return (
    <footer
      style={{
        height: 'var(--player-height)',
        backgroundColor: 'var(--bg-player)',
        backdropFilter: 'blur(20px)',
        borderTop: '1px solid var(--border-subtle)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0 28px',
        zIndex: 100,
        userSelect: 'none',
        position: 'relative',
      }}
    >
      {/* 1. Left: Track Metadata & Artwork */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '14px', width: '30%', minWidth: 0 }}>
        <img
          src={api.getArtworkUrl('song', currentSong.id, 96, 96)}
          alt={currentSong.title}
          style={{
            width: '52px',
            height: '52px',
            borderRadius: 'var(--radius-sm)',
            objectFit: 'cover',
            backgroundColor: 'var(--bg-surface)',
            border: '1px solid var(--border-subtle)',
            boxShadow: 'var(--shadow-sm)',
            flexShrink: 0,
          }}
          onError={(e) => {
            (e.target as HTMLImageElement).src =
              'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="52" height="52" fill="%231e293b"><rect width="52" height="52"/></svg>';
          }}
        />
        <div style={{ overflow: 'hidden', minWidth: 0 }}>
          <div
            style={{
              fontWeight: 600,
              fontSize: '14px',
              color: 'var(--text-primary)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
            }}
          >
            {currentSong.title}
          </div>
          <div
            style={{
              fontSize: '12px',
              color: 'var(--text-muted)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              marginTop: '2px',
            }}
          >
            {currentSong.artist || currentSong.album || 'Tamil MP3'}
          </div>
        </div>

        <QualityBadge quality={currentSong.quality} />

        <button
          onClick={handleToggleFavorite}
          style={{
            color: isFav ? 'var(--color-error)' : 'var(--text-muted)',
            cursor: 'pointer',
            padding: '4px',
            transition: 'color var(--transition-fast), transform var(--transition-fast)',
          }}
          title={isFav ? 'Remove from favorites' : 'Add to favorites'}
        >
          <Heart size={18} fill={isFav ? 'currentColor' : 'none'} />
        </button>
      </div>

      {/* 2. Middle: Transport Controls & Scrubber */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          gap: '6px',
          width: '40%',
          maxWidth: '560px',
        }}
      >
        {/* Buttons */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
          <button
            onClick={playPrevious}
            className="btn-icon"
            style={{ width: '32px', height: '32px' }}
            title="Previous track"
          >
            <SkipBack size={18} />
          </button>

          <button
            onClick={togglePlay}
            className="btn-icon-primary"
            style={{
              width: '42px',
              height: '42px',
              borderRadius: '50%',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
            }}
            title={isPlaying ? 'Pause' : 'Play'}
          >
            {isLoading ? (
              <Loader2 size={20} className="animate-spin" />
            ) : isPlaying ? (
              <Pause size={20} fill="currentColor" />
            ) : (
              <Play size={20} fill="currentColor" style={{ marginLeft: '2px' }} />
            )}
          </button>

          <button
            onClick={playNext}
            className="btn-icon"
            style={{ width: '32px', height: '32px' }}
            title="Next track"
          >
            <SkipForward size={18} />
          </button>
        </div>

        {/* Progress Bar & Timestamps */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', width: '100%' }}>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', width: '32px', textAlign: 'right' }}>
            {formatTime(progress)}
          </span>
          <div
            style={{
              flex: 1,
              height: '6px',
              backgroundColor: 'rgba(255, 255, 255, 0.1)',
              borderRadius: 'var(--radius-pill)',
              position: 'relative',
              cursor: 'pointer',
            }}
            onClick={(e) => {
              const rect = e.currentTarget.getBoundingClientRect();
              const clickX = e.clientX - rect.left;
              const ratio = clickX / rect.width;
              seek(ratio * duration);
            }}
          >
            <div
              style={{
                width: `${progressPercent}%`,
                height: '100%',
                backgroundColor: 'var(--accent-primary)',
                borderRadius: 'var(--radius-pill)',
                boxShadow: '0 0 8px var(--accent-primary-glow)',
                transition: 'width 100ms linear',
              }}
            />
          </div>
          <span style={{ fontSize: '11px', color: 'var(--text-muted)', width: '32px' }}>
            {formatTime(duration)}
          </span>
        </div>
      </div>

      {/* 3. Right: Volume & Playback Indicator */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'flex-end',
          gap: '12px',
          width: '30%',
        }}
      >
        {/* Equalizer animation when playing */}
        {isPlaying && (
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: '16px', marginRight: '8px' }}>
            <span style={{ width: '3px', background: 'var(--accent-secondary)', borderRadius: '1px', animation: 'equalizer-bounce 0.8s infinite ease-in-out' }} />
            <span style={{ width: '3px', background: 'var(--accent-primary)', borderRadius: '1px', animation: 'equalizer-bounce 0.6s infinite ease-in-out 0.2s' }} />
            <span style={{ width: '3px', background: 'var(--accent-secondary)', borderRadius: '1px', animation: 'equalizer-bounce 0.9s infinite ease-in-out 0.4s' }} />
          </div>
        )}

        <button
          onClick={toggleMute}
          className="btn-icon"
          style={{ width: '32px', height: '32px' }}
          title={isMuted ? 'Unmute' : 'Mute'}
        >
          {isMuted || volume === 0 ? <VolumeX size={18} /> : <Volume2 size={18} />}
        </button>

        <input
          type="range"
          min="0"
          max="1"
          step="0.01"
          value={isMuted ? 0 : volume}
          onChange={(e) => setVolume(parseFloat(e.target.value))}
          style={{
            width: '90px',
            accentColor: 'var(--accent-primary)',
            cursor: 'pointer',
          }}
        />
      </div>
    </footer>
  );
};
