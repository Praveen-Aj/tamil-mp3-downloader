import React, { useEffect, useState } from 'react';
import { ArrowLeft, Play, Download, Users, CheckCircle2 } from 'lucide-react';
import { artistsApi, downloadsApi } from '../../api/endpoints';
import { Artist, Song } from '../../api/types';
import { useApp } from '../../context/AppContext';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { Button } from '../common/Button';
import { QualityBadge, StateBadge } from '../common/Badge';
import { api } from '../../api/client';

export const ArtistDetailView: React.FC = () => {
  const { selectedEntityId, navigateTo, showToast, refreshStats } = useApp();
  const { playSong } = useAudioPlayer();

  const [artist, setArtist] = useState<Artist | null>(null);
  const [songs, setSongs] = useState<Song[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!selectedEntityId) return;
    const loadDetails = async () => {
      setLoading(true);
      try {
        const res = await artistsApi.getArtistSongs(Number(selectedEntityId));
        if (res.success && res.data) {
          setArtist(res.data.artist);
          setSongs(res.data.songs || []);
        }
      } catch (err: any) {
        showToast(err.message || 'Failed to load artist details', 'error');
      } finally {
        setLoading(false);
      }
    };
    loadDetails();
  }, [selectedEntityId, showToast]);

  const handleDownloadAll = async () => {
    if (!selectedEntityId || !artist) return;
    try {
      const res = await artistsApi.startDownload(Number(selectedEntityId));
      if (res.success) {
        showToast(`Queued ${res.data.queued_count} songs by "${artist.name}"`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue download', 'error');
    }
  };

  const handleDownloadSong = async (songId: number) => {
    try {
      const res = await downloadsApi.queueSongs([songId]);
      if (res.success) {
        showToast('Song queued for download', 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to download song', 'error');
    }
  };

  if (!selectedEntityId || (!loading && !artist)) {
    return (
      <div style={{ padding: '32px' }}>
        <Button variant="ghost" onClick={() => navigateTo('artists')}>
          <ArrowLeft size={16} /> Back to Artists
        </Button>
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          Artist not found.
        </div>
      </div>
    );
  }

  return (
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '28px' }}>
      <Button variant="ghost" onClick={() => navigateTo('artists')} style={{ alignSelf: 'flex-start' }}>
        <ArrowLeft size={16} /> Back to Artists
      </Button>

      {/* Hero Artist Banner */}
      <div
        className="glass-panel"
        style={{
          padding: '28px 32px',
          display: 'flex',
          gap: '28px',
          alignItems: 'center',
          flexWrap: 'wrap',
          background: 'linear-gradient(135deg, rgba(15, 23, 42, 0.6) 0%, rgba(17, 26, 46, 0.8) 100%)',
        }}
      >
        <img
          src={api.getArtworkUrl('artist', Number(selectedEntityId), 180, 180)}
          alt={artist?.name}
          style={{
            width: '130px',
            height: '130px',
            borderRadius: '50%',
            objectFit: 'cover',
            boxShadow: 'var(--shadow-lg)',
            border: '2px solid var(--border-medium)',
          }}
          onError={(e) => {
            (e.target as HTMLImageElement).src =
              'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="130" height="130" fill="%230f172a"><circle cx="65" cy="65" r="65"/></svg>';
          }}
        />

        <div style={{ flex: 1, minWidth: '240px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: '#f59e0b', fontSize: '13px', fontWeight: 600 }}>
            <Users size={15} /> ARTIST DISCOGRAPHY
          </div>
          <h2 className="title-display" style={{ fontSize: '32px', fontWeight: 800, marginTop: '4px' }}>
            {artist?.name}
          </h2>
          <div style={{ fontSize: '14px', color: 'var(--text-secondary)', marginTop: '6px' }}>
            {artist?.role || 'Composer & Singer'} • {songs.length} Tracks in Catalog
          </div>

          <div style={{ marginTop: '16px' }}>
            <Button variant="primary" onClick={handleDownloadAll}>
              <Download size={16} /> Download All Songs
            </Button>
          </div>
        </div>
      </div>

      {/* Tracklist Table */}
      <div className="glass-panel" style={{ overflow: 'hidden' }}>
        <table className="data-table">
          <thead>
            <tr>
              <th style={{ width: '50px' }}>Play</th>
              <th>Track Title</th>
              <th>Soundtrack / Album</th>
              <th>Quality</th>
              <th>Status</th>
              <th style={{ textAlign: 'right', width: '100px' }}>Action</th>
            </tr>
          </thead>
          <tbody>
            {songs.map((song) => (
              <tr key={song.id}>
                <td>
                  <button
                    onClick={() => playSong(song)}
                    className="btn-icon"
                    style={{ width: '32px', height: '32px' }}
                    title="Play track"
                  >
                    <Play size={14} fill="currentColor" />
                  </button>
                </td>
                <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{song.title}</td>
                <td style={{ color: 'var(--text-secondary)' }}>{song.album || '—'}</td>
                <td>
                  <QualityBadge quality={song.quality} />
                </td>
                <td>
                  <StateBadge state={song.state} />
                </td>
                <td style={{ textAlign: 'right' }}>
                  {song.state !== 'OWNED' ? (
                    <Button size="sm" variant="secondary" onClick={() => handleDownloadSong(song.id)}>
                      <Download size={13} />
                    </Button>
                  ) : (
                    <span style={{ color: 'var(--color-success)', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                      <CheckCircle2 size={14} /> Saved
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
