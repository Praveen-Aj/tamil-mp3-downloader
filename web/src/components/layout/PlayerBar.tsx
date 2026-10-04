import React, { useState, useEffect } from 'react';
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
  ListMusic,
  X,
  Trash2,
  Download,
  CheckCircle2,
} from 'lucide-react';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { useApp } from '../../context/AppContext';
import { api } from '../../api/client';
import { QualityBadge } from '../common/Badge';
import { songsApi, downloadsApi } from '../../api/endpoints';

export const PlayerBar: React.FC = () => {
  const {
    currentSong,
    isPlaying,
    isLoading,
    progress,
    duration,
    volume,
    isMuted,
    queue,
    isPlayerHidden,
    hidePlayer,
    showPlayer,
    togglePlay,
    seek,
    setVolume,
    toggleMute,
    playNext,
    playPrevious,
    playSong,
    removeFromQueue,
    clearQueue,
  } = useAudioPlayer();

  const { showToast, refreshStats } = useApp();
  const [isFav, setIsFav] = useState(false);
  const [isQueueOpen, setIsQueueOpen] = useState(false);

  // Sync favorite state
  useEffect(() => {
    if (currentSong) {
      setIsFav(Boolean(currentSong.is_favorite));
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

  const handleDownloadCurrentSong = async () => {
    if (!currentSong) return;
    try {
      const res = await downloadsApi.queueSongs([currentSong.id]);
      if (res.success) {
        showToast(`Queued "${currentSong.title}" for download`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to download song', 'error');
    }
  };

  const formatTime = (seconds: number) => {
    if (!seconds || isNaN(seconds)) return '0:00';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  // If user explicitly hid the player bar, do not display it (audio continues streaming in background)
  if (isPlayerHidden) {
    return null;
  }

  // 1. Idle state: Compact, elegant bar
  if (!currentSong) {
    return (
      <footer
        className="player-bar-idle"
        style={{
          height: '48px',
          backgroundColor: 'var(--bg-player)',
          backdropFilter: 'blur(20px)',
          borderTop: '1px solid var(--border-subtle)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          fontSize: '12px',
          userSelect: 'none',
          padding: '0 24px',
          zIndex: 100,
          transition: 'height var(--transition-normal)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Music size={14} color="var(--accent-primary)" />
          <span>Select any track to stream in high fidelity (320 kbps MP3)</span>
        </div>
      </footer>
    );
  }

  const progressPercent = duration > 0 ? (progress / duration) * 100 : 0;
  const remainingTime = duration > progress ? duration - progress : 0;

  return (
    <>
      <footer
        className="player-bar-container"
        style={{
          height: 'var(--player-height)',
          backgroundColor: 'var(--bg-player)',
          backdropFilter: 'blur(24px)',
          WebkitBackdropFilter: 'blur(24px)',
          borderTop: '1px solid var(--border-medium)',
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
        <div className="player-track-info" style={{ display: 'flex', alignItems: 'center', gap: '14px', width: '32%', minWidth: 0 }}>
          <img
            src={api.getArtworkUrl('song', currentSong.id, 120, 120)}
            alt={currentSong.title}
            style={{
              width: '56px',
              height: '56px',
              borderRadius: 'var(--radius-md)',
              objectFit: 'cover',
              backgroundColor: 'var(--bg-surface-active)',
              border: '1px solid var(--border-subtle)',
              boxShadow: '0 4px 12px rgba(0, 0, 0, 0.4)',
              flexShrink: 0,
            }}
            onError={(e) => {
              (e.target as HTMLImageElement).src =
                'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" fill="%2311141c"><rect width="56" height="56"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="16">🎵</text></svg>';
            }}
          />
          <div style={{ overflow: 'hidden', minWidth: 0, flex: 1 }}>
            <div
              style={{
                fontWeight: 700,
                fontSize: '14px',
                color: 'var(--text-primary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
              }}
              title={currentSong.title}
            >
              {currentSong.title}
            </div>
            <div
              style={{
                fontSize: '12px',
                color: 'var(--text-secondary)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                marginTop: '2px',
              }}
              title={`${currentSong.artist || 'Unknown'} • ${currentSong.album || 'Soundtrack'}`}
            >
              {currentSong.artist || 'Unknown'} {currentSong.album ? `• ${currentSong.album}` : ''}
            </div>
          </div>

          <QualityBadge
            quality={currentSong.quality}
            isDownloaded={currentSong.has_file || currentSong.state === 'OWNED'}
          />

          <button
            onClick={handleToggleFavorite}
            style={{
              color: isFav ? 'var(--color-error)' : 'var(--text-muted)',
              cursor: 'pointer',
              padding: '6px',
              border: 'none',
              background: 'none',
              transition: 'color var(--transition-fast), transform var(--transition-fast)',
            }}
            title={isFav ? 'Remove from favorites' : 'Add to favorites'}
            aria-label={isFav ? 'Remove from favorites' : 'Add to favorites'}
          >
            <Heart size={18} fill={isFav ? 'currentColor' : 'none'} />
          </button>

          {!(currentSong.has_file || currentSong.state === 'OWNED') ? (
            <button
              onClick={handleDownloadCurrentSong}
              className="btn-icon"
              style={{ width: '32px', height: '32px', color: 'var(--accent-primary)' }}
              title="Download track to local library"
              aria-label="Download track"
            >
              <Download size={15} />
            </button>
          ) : (
            <span
              style={{ color: 'var(--color-success)', display: 'inline-flex', padding: '4px' }}
              title="Track is downloaded in local library"
            >
              <CheckCircle2 size={16} />
            </span>
          )}
        </div>

        {/* 2. Middle: Transport Controls & Scrubber */}
        <div
          className="player-controls-wrap"
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
              aria-label="Previous track"
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
              aria-label={isPlaying ? 'Pause' : 'Play'}
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
              aria-label="Next track"
            >
              <SkipForward size={18} />
            </button>
          </div>

          {/* Progress Bar & Timestamps */}
          <div className="player-progress-desktop" style={{ display: 'flex', alignItems: 'center', gap: '10px', width: '100%' }}>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', width: '36px', textAlign: 'right', fontVariantNumeric: 'tabular-nums' }}>
              {formatTime(progress)}
            </span>
            <div
              style={{
                flex: 1,
                height: '6px',
                backgroundColor: 'rgba(255, 255, 255, 0.12)',
                borderRadius: 'var(--radius-pill)',
                position: 'relative',
                cursor: 'pointer',
              }}
              onClick={(e) => {
                const rect = e.currentTarget.getBoundingClientRect();
                const clickX = e.clientX - rect.left;
                const ratio = Math.max(0, Math.min(1, clickX / rect.width));
                seek(ratio * duration);
              }}
              role="slider"
              aria-valuemin={0}
              aria-valuemax={duration || 100}
              aria-valuenow={progress}
              aria-label="Audio scrubber"
            >
              <div
                style={{
                  width: `${progressPercent}%`,
                  height: '100%',
                  backgroundColor: 'var(--accent-primary)',
                  borderRadius: 'var(--radius-pill)',
                  position: 'relative',
                  transition: 'width 80ms linear',
                }}
              >
                <div
                  style={{
                    position: 'absolute',
                    right: '-4px',
                    top: '50%',
                    transform: 'translateY(-50%)',
                    width: '10px',
                    height: '10px',
                    borderRadius: '50%',
                    backgroundColor: '#ffffff',
                    boxShadow: '0 1px 4px rgba(0, 0, 0, 0.5)',
                  }}
                />
              </div>
            </div>
            <span style={{ fontSize: '11px', color: 'var(--text-muted)', width: '36px', fontVariantNumeric: 'tabular-nums' }}>
              -{formatTime(remainingTime)}
            </span>
          </div>
        </div>

        {/* 3. Right: Volume, Queue Drawer Toggle & Equalizer */}
        <div
          className="player-volume-wrap"
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
            <div
              style={{ display: 'flex', alignItems: 'flex-end', gap: '2px', height: '16px', marginRight: '6px' }}
              title="Streaming active"
            >
              <span style={{ width: '3px', background: 'var(--accent-secondary)', borderRadius: '1px', animation: 'equalizer-bounce 0.8s infinite ease-in-out' }} />
              <span style={{ width: '3px', background: 'var(--accent-primary)', borderRadius: '1px', animation: 'equalizer-bounce 0.6s infinite ease-in-out 0.2s' }} />
              <span style={{ width: '3px', background: 'var(--accent-secondary)', borderRadius: '1px', animation: 'equalizer-bounce 0.9s infinite ease-in-out 0.4s' }} />
            </div>
          )}

          {/* Queue Drawer Toggle */}
          <button
            onClick={() => setIsQueueOpen(!isQueueOpen)}
            className="btn-icon"
            style={{
              width: '34px',
              height: '34px',
              backgroundColor: isQueueOpen ? 'rgba(212, 163, 89, 0.16)' : 'transparent',
              color: isQueueOpen ? 'var(--accent-primary)' : 'var(--text-secondary)',
              position: 'relative',
            }}
            title="Toggle playback queue"
            aria-label="Toggle playback queue"
          >
            <ListMusic size={18} />
            {queue.length > 0 && (
              <span
                style={{
                  position: 'absolute',
                  top: '4px',
                  right: '4px',
                  width: '6px',
                  height: '6px',
                  borderRadius: '50%',
                  backgroundColor: 'var(--accent-primary)',
                }}
              />
            )}
          </button>

          {/* Volume button */}
          <button
            onClick={toggleMute}
            className="btn-icon"
            style={{ width: '32px', height: '32px' }}
            title={isMuted ? 'Unmute' : 'Mute'}
            aria-label={isMuted ? 'Unmute' : 'Mute'}
          >
            {isMuted || volume === 0 ? <VolumeX size={18} /> : <Volume2 size={18} />}
          </button>

          {/* Volume slider */}
          <input
            type="range"
            min="0"
            max="1"
            step="0.01"
            value={isMuted ? 0 : volume}
            onChange={(e) => setVolume(parseFloat(e.target.value))}
            className="audio-range"
            style={{
              width: '84px',
            }}
            aria-label="Volume Slider"
          />

          {/* Hide / Close player button */}
          <button
            onClick={hidePlayer}
            className="btn-icon"
            style={{ width: '32px', height: '32px', color: 'var(--text-muted)', marginLeft: '6px' }}
            title="Hide player"
            aria-label="Hide player"
          >
            <X size={18} />
          </button>
        </div>
      </footer>

      {/* Slide-Up Queue Drawer */}
      {isQueueOpen && (
        <div className="queue-drawer">
          <div
            style={{
              padding: '14px 18px',
              borderBottom: '1px solid var(--border-subtle)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              backgroundColor: 'var(--bg-surface-elevated)',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <ListMusic size={16} color="var(--accent-primary)" />
              <span style={{ fontWeight: 700, fontSize: '13px', color: 'var(--text-primary)' }}>
                Play Queue ({queue.length})
              </span>
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
              {queue.length > 0 && (
                <button
                  onClick={clearQueue}
                  className="btn-ghost"
                  style={{ fontSize: '11px', padding: '4px 8px', borderRadius: '4px' }}
                  title="Clear Queue"
                >
                  <Trash2 size={12} /> Clear
                </button>
              )}
              <button
                onClick={() => setIsQueueOpen(false)}
                className="btn-icon"
                style={{ width: '28px', height: '28px' }}
                aria-label="Close queue"
              >
                <X size={15} />
              </button>
            </div>
          </div>

          <div style={{ overflowY: 'auto', flex: 1, padding: '8px' }}>
            {/* Now Playing Row */}
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--accent-primary)', textTransform: 'uppercase', padding: '6px 8px' }}>
              Now Playing
            </div>
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '8px',
                borderRadius: 'var(--radius-sm)',
                backgroundColor: 'rgba(212, 163, 89, 0.12)',
                border: '1px solid rgba(212, 163, 89, 0.25)',
                marginBottom: '10px',
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1 }}>
                <img
                  src={api.getArtworkUrl('song', currentSong.id, 36, 36)}
                  alt={currentSong.title}
                  style={{ width: '32px', height: '32px', borderRadius: '4px', objectFit: 'cover' }}
                  onError={(e) => {
                    (e.target as HTMLImageElement).src =
                      'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" fill="%231e293b"><rect width="32" height="32"/></svg>';
                  }}
                />
                <div style={{ minWidth: 0, flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: '12px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {currentSong.title}
                  </div>
                  <div style={{ fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                    {currentSong.artist || 'Unknown'}
                  </div>
                </div>
              </div>
              <QualityBadge quality={currentSong.quality} />
            </div>

            {/* Next in Queue */}
            <div style={{ fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', padding: '6px 8px' }}>
              Next Up
            </div>
            {queue.length === 0 ? (
              <div style={{ padding: '20px 8px', textAlign: 'center', color: 'var(--text-muted)', fontSize: '12px' }}>
                Queue is empty. Play a song from a playlist or library to queue tracks!
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                {queue.map((song, idx) => (
                  <div
                    key={`${song.id}-${idx}`}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '6px 8px',
                      borderRadius: 'var(--radius-sm)',
                      backgroundColor: 'rgba(255, 255, 255, 0.02)',
                      transition: 'background var(--transition-fast)',
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = 'var(--bg-surface-hover)')}
                    onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.02)')}
                  >
                    <div
                      onClick={() => {
                        removeFromQueue(idx);
                        playSong(song);
                      }}
                      style={{ display: 'flex', alignItems: 'center', gap: '8px', minWidth: 0, flex: 1, cursor: 'pointer' }}
                    >
                      <img
                        src={api.getArtworkUrl('song', song.id, 32, 32)}
                        alt={song.title}
                        style={{ width: '28px', height: '28px', borderRadius: '4px', objectFit: 'cover' }}
                        onError={(e) => {
                          (e.target as HTMLImageElement).src =
                            'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="28" height="28" fill="%231e293b"><rect width="28" height="28"/></svg>';
                        }}
                      />
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontWeight: 500, fontSize: '12px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {song.title}
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--text-muted)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                          {song.artist || 'Unknown'}
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => removeFromQueue(idx)}
                      className="btn-icon"
                      style={{ width: '24px', height: '24px', color: 'var(--text-muted)' }}
                      title="Remove from queue"
                      aria-label={`Remove ${song.title} from queue`}
                    >
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
};
