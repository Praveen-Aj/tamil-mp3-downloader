import React, { useState } from 'react';
import { Play, Pause, Download, Heart, CheckCircle2, Music, Loader2 } from 'lucide-react';
import { Song } from '../../api/types';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { useApp } from '../../context/AppContext';
import { songsApi, downloadsApi } from '../../api/endpoints';
import { api } from '../../api/client';

interface TrackRowProps {
  song: Song;
  playlistContext?: Song[];
  index?: number;
  showCover?: boolean;
  onNavigateMovie?: (movieId: number) => void;
  onNavigateArtist?: (artistId: number) => void;
  isSelected?: boolean;
  onToggleSelect?: (songId: number) => void;
  showCheckbox?: boolean;
}

export const TrackRow: React.FC<TrackRowProps> = ({
  song,
  playlistContext = [],
  index,
  showCover = true,
  onNavigateMovie,
  onNavigateArtist,
  isSelected = false,
  onToggleSelect,
  showCheckbox = false,
}) => {
  const { currentSong, isPlaying, playSong, togglePlay } = useAudioPlayer();
  const { showToast, refreshStats } = useApp();

  const [isFav, setIsFav] = useState(Boolean(song.is_favorite));
  const [downloading, setDownloading] = useState(false);

  const isCurrent = currentSong?.id === song.id;
  const isDownloaded = Boolean(song.has_file || song.file_path || song.state === 'OWNED');

  const handlePlayClick = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (isCurrent) {
      togglePlay();
    } else {
      playSong(song, playlistContext.length > 0 ? playlistContext : [song]);
    }
  };

  const handleToggleFav = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const nextFav = !isFav;
      setIsFav(nextFav);
      await songsApi.toggleFavorite(song.id, nextFav);
    } catch (err) {
      setIsFav(!isFav);
    }
  };

  const handleDownload = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setDownloading(true);
    try {
      const res = await downloadsApi.queueSongs([song.id]);
      if (res.success) {
        showToast(`Queued "${song.title}" for download`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue download', 'error');
    } finally {
      setDownloading(false);
    }
  };

  const formatDuration = (seconds?: number) => {
    if (!seconds || isNaN(seconds)) return '--:--';
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}:${secs < 10 ? '0' : ''}${secs}`;
  };

  return (
    <div
      className={`track-row ${isCurrent ? 'active' : ''}`}
      onClick={() => playSong(song, playlistContext.length > 0 ? playlistContext : [song])}
      style={{ cursor: 'pointer' }}
    >
      {/* Checkbox for batch actions */}
      {showCheckbox && (
        <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', alignItems: 'center' }}>
          <input
            type="checkbox"
            checked={isSelected}
            onChange={() => onToggleSelect && onToggleSelect(song.id)}
            aria-label={`Select track ${song.title}`}
          />
        </div>
      )}

      {/* Track Index or Playing Indicator */}
      <div
        style={{
          width: '24px',
          textAlign: 'center',
          fontSize: '13px',
          color: isCurrent ? 'var(--accent-primary)' : 'var(--text-muted)',
          fontWeight: isCurrent ? 600 : 400,
          fontFamily: 'var(--font-mono)',
        }}
      >
        {isCurrent ? (
          isPlaying ? (
            <span style={{ color: 'var(--accent-primary)', fontSize: '14px' }}>▶</span>
          ) : (
            <Pause size={14} style={{ color: 'var(--accent-primary)' }} />
          )
        ) : (
          index !== undefined ? index + 1 : ''
        )}
      </div>

      {/* Optional Album/Movie Cover Artwork */}
      {showCover && (
        <div
          style={{
            width: '44px',
            height: '44px',
            borderRadius: 'var(--radius-sm)',
            overflow: 'hidden',
            backgroundColor: 'var(--bg-inset)',
            flexShrink: 0,
            position: 'relative',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <img
            src={api.getArtworkUrl('song', song.id, 88, 88)}
            alt={song.title}
            style={{ width: '100%', height: '100%', objectFit: 'cover' }}
            loading="lazy"
            onError={(e) => {
              (e.target as HTMLImageElement).src =
                'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="44" height="44" fill="%23101014"><rect width="44" height="44"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%23D4A359" font-size="14">🎵</text></svg>';
            }}
          />
        </div>
      )}

      {/* Track Info (Title & Movie/Soundtrack / Artist) */}
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: '2px' }}>
        <div
          style={{
            fontSize: '14px',
            fontWeight: 600,
            color: isCurrent ? 'var(--accent-primary)' : 'var(--text-primary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {song.title}
        </div>
        <div
          style={{
            fontSize: '12px',
            color: 'var(--text-secondary)',
            whiteSpace: 'nowrap',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          }}
        >
          {song.album || 'Tamil Track'}
          {song.artist && ` • ${song.artist}`}
        </div>
      </div>

      {/* Quality Badge */}
      <div style={{ flexShrink: 0 }}>
        {song.quality ? (
          <span
            className="font-mono"
            style={{
              fontSize: '11px',
              color: song.quality >= 320 ? 'var(--color-success)' : 'var(--text-muted)',
              padding: '2px 6px',
              borderRadius: 'var(--radius-xs)',
              backgroundColor: song.quality >= 320 ? 'var(--color-success-bg)' : 'transparent',
            }}
          >
            {song.quality} kbps
          </span>
        ) : (
          <span className="font-mono" style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
            320 kbps
          </span>
        )}
      </div>

      {/* Duration */}
      <div
        className="font-mono"
        style={{
          width: '48px',
          textAlign: 'right',
          fontSize: '12px',
          color: 'var(--text-muted)',
          flexShrink: 0,
        }}
      >
        {formatDuration(song.duration_sec)}
      </div>

      {/* Downloaded State Indicator or Quick Download CTA */}
      <div style={{ width: '32px', display: 'flex', justifyContent: 'center', flexShrink: 0 }}>
        {isDownloaded ? (
          <span title="Downloaded (Local)">
            <CheckCircle2 size={16} style={{ color: 'var(--color-success)' }} />
          </span>
        ) : downloading ? (
          <Loader2 size={16} className="animate-spin" style={{ color: 'var(--accent-primary)' }} />
        ) : (
          <button
            className="btn-icon"
            style={{ width: '28px', height: '28px' }}
            onClick={handleDownload}
            title="Download track (320 kbps)"
            aria-label={`Download ${song.title}`}
          >
            <Download size={14} />
          </button>
        )}
      </div>

      {/* Favorite Heart Toggle */}
      <div style={{ width: '28px', display: 'flex', justifyContent: 'center', flexShrink: 0 }}>
        <button
          className="btn-icon"
          style={{ width: '28px', height: '28px', color: isFav ? 'var(--color-error)' : 'var(--text-muted)' }}
          onClick={handleToggleFav}
          aria-label={isFav ? 'Remove from favorites' : 'Add to favorites'}
        >
          <Heart size={15} fill={isFav ? 'currentColor' : 'none'} />
        </button>
      </div>
    </div>
  );
};
