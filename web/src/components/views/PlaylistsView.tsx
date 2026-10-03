import React, { useEffect, useState, useCallback } from 'react';
import {
  ListMusic,
  Plus,
  Download,
  Trash2,
  Music,
  ArrowLeft,
  Play,
  FolderOpen,
  X,
} from 'lucide-react';
import { playlistsApi, downloadsApi, songsApi } from '../../api/endpoints';
import { Playlist, Song } from '../../api/types';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Modal } from '../common/Modal';
import { QualityBadge, DownloadStateBadge } from '../common/Badge';
import { useApp } from '../../context/AppContext';
import { useAudioPlayer } from '../../context/AudioPlayerContext';
import { api } from '../../api/client';

export const PlaylistsView: React.FC = () => {
  const { showToast, refreshStats } = useApp();
  const { playSong } = useAudioPlayer();
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  // Selected playlist for viewing / managing tracks
  const [selectedPlaylist, setSelectedPlaylist] = useState<Playlist | null>(null);
  const [playlistSongs, setPlaylistSongs] = useState<Song[]>([]);
  const [loadingSongs, setLoadingSongs] = useState(false);

  // Deletion confirm modal state
  const [deleteModalPlaylist, setDeleteModalPlaylist] = useState<Playlist | null>(null);

  const loadPlaylists = useCallback(async () => {
    setLoading(true);
    try {
      const res = await playlistsApi.getPlaylists();
      if (res.success && res.data) {
        // Filter out test/demo playlists from the UI
        const validPlaylists = (res.data.items || []).filter(
          (pl: Playlist) => !pl.name.toLowerCase().includes('test')
        );
        setPlaylists(validPlaylists);
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to load playlists', 'error');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  useEffect(() => {
    loadPlaylists();
  }, [loadPlaylists]);

  const loadPlaylistDetails = useCallback(async (plId: number) => {
    setLoadingSongs(true);
    try {
      const res = await playlistsApi.getPlaylist(plId);
      if (res.success && res.data) {
        const rawSongs = (res.data as any).songs || (res.data as any).items || [];
        setPlaylistSongs(rawSongs);
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to load playlist tracks', 'error');
    } finally {
      setLoadingSongs(false);
    }
  }, [showToast]);

  const handleOpenPlaylist = (pl: Playlist) => {
    setSelectedPlaylist(pl);
    loadPlaylistDetails(pl.id);
  };

  const handleCreate = async () => {
    if (!name.trim()) {
      showToast('Please enter a playlist name', 'warning');
      return;
    }
    try {
      const res = await playlistsApi.createPlaylist(name.trim(), description.trim());
      if (res.success) {
        showToast(`Created playlist "${name}"`, 'success');
        setIsModalOpen(false);
        setName('');
        setDescription('');
        refreshStats();
        loadPlaylists();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to create playlist', 'error');
    }
  };

  const handleDownload = async (e: React.MouseEvent, plId: number, plName: string) => {
    e.stopPropagation();
    try {
      const res = await playlistsApi.startDownload(plId);
      if (res.success) {
        showToast(`Queued ${res.data.queued_count} songs from "${plName}"`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to download playlist', 'error');
    }
  };

  const confirmDeletePlaylist = async () => {
    if (!deleteModalPlaylist) return;
    const plId = deleteModalPlaylist.id;
    try {
      await playlistsApi.deletePlaylist(plId);
      showToast('Playlist deleted successfully', 'info');
      if (selectedPlaylist?.id === plId) {
        setSelectedPlaylist(null);
      }
      setDeleteModalPlaylist(null);
      refreshStats();
      loadPlaylists();
    } catch (err: any) {
      showToast(err.message || 'Failed to delete playlist', 'error');
    }
  };

  const handleRemoveSong = async (songId: number, songTitle: string) => {
    if (!selectedPlaylist) return;
    try {
      await playlistsApi.removeSong(selectedPlaylist.id, songId);
      showToast(`Removed "${songTitle}" from playlist`, 'info');
      loadPlaylistDetails(selectedPlaylist.id);
      loadPlaylists();
      refreshStats();
    } catch (err: any) {
      showToast(err.message || 'Failed to remove song from playlist', 'error');
    }
  };

  const handleQueueSingle = async (songId: number, songTitle: string) => {
    try {
      const res = await downloadsApi.queueSongs([songId]);
      if (res.success) {
        showToast(`Queued "${songTitle}" for download`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue download', 'error');
    }
  };

  const handleOpenFolder = async (songId: number) => {
    try {
      await songsApi.openFolder(songId);
    } catch (err: any) {
      showToast(err.message || 'Failed to open file folder', 'error');
    }
  };

  // If a playlist is selected, show the Drilldown / Detail View
  if (selectedPlaylist) {
    return (
      <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Back navigation & Header */}
        <div
          className="glass-panel"
          style={{
            padding: '24px 28px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            flexWrap: 'wrap',
            gap: '16px',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <Button variant="ghost" onClick={() => setSelectedPlaylist(null)} aria-label="Back to playlists" style={{ padding: '6px 12px', fontSize: '13px' }}>
              <ArrowLeft size={15} /> Playlists
            </Button>
            <div
              style={{
                width: '44px',
                height: '44px',
                borderRadius: '10px',
                backgroundColor: 'rgba(139, 124, 248, 0.12)',
                border: '1px solid rgba(139, 124, 248, 0.2)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              <Music size={22} color="var(--accent-primary)" />
            </div>
            <div>
              <h2 className="title-display" style={{ fontSize: '20px', fontWeight: 800, margin: 0, color: '#f8fafc' }}>
                {selectedPlaylist.name}
              </h2>
              <div style={{ fontSize: '12.5px', color: 'var(--text-muted)', marginTop: '2px' }}>
                {selectedPlaylist.description || 'Custom Playlist'} · {playlistSongs.length} {playlistSongs.length === 1 ? 'song' : 'songs'}
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
            {playlistSongs.length > 0 && (
              <>
                <Button
                  variant="secondary"
                  onClick={() => playSong(playlistSongs[0], playlistSongs)}
                  aria-label="Play Playlist"
                >
                  <Play size={15} fill="currentColor" /> Play All
                </Button>
                <Button
                  variant="primary"
                  onClick={(e) => handleDownload(e, selectedPlaylist.id, selectedPlaylist.name)}
                  aria-label="Download Playlist"
                >
                  <Download size={15} /> Download All
                </Button>
              </>
            )}
            <Button
              variant="ghost"
              onClick={() => setDeleteModalPlaylist(selectedPlaylist)}
              style={{ color: 'var(--color-error)' }}
              aria-label="Delete Playlist"
            >
              <Trash2 size={16} /> Delete
            </Button>
          </div>
        </div>

        {/* Songs List */}
        <div className="glass-panel" style={{ overflow: 'hidden' }}>
          {loadingSongs ? (
            <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
              Loading songs in playlist...
            </div>
          ) : playlistSongs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
              No tracks in this playlist yet. Add songs from Song Library or Album views!
            </div>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Track</th>
                  <th>Soundtrack / Album</th>
                  <th style={{ width: '115px' }}>Status</th>
                  <th style={{ width: '85px' }}>Quality</th>
                  <th style={{ textAlign: 'right', width: '90px' }}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {playlistSongs.map((song) => {
                  const sId = (song as any).id || (song as any).song_id;
                  const isOwned =
                    song.has_file ||
                    song.download_state === 'DOWNLOADED' ||
                    song.state === 'OWNED' ||
                    song.state === 'owned' ||
                    Boolean(song.file_path);

                  return (
                    <tr key={sId}>
                      {/* Track: Art with play overlay + Title + Artist */}
                      <td style={{ minWidth: '220px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                          <div
                            onClick={() => playSong(song, playlistSongs)}
                            style={{
                              width: '40px',
                              height: '40px',
                              borderRadius: 'var(--radius-sm)',
                              overflow: 'hidden',
                              position: 'relative',
                              backgroundColor: '#16161a',
                              cursor: 'pointer',
                              flexShrink: 0,
                            }}
                            className="track-art-wrap"
                            title={`Play ${song.title}`}
                          >
                            <img
                              src={api.getArtworkUrl('song', sId, 80, 80)}
                              alt={song.title}
                              style={{ width: '100%', height: '100%', objectFit: 'cover' }}
                              onError={(e) => {
                                (e.target as HTMLImageElement).src =
                                  'data:image/svg+xml;utf8,<svg xmlns="http://www.w3.org/2000/svg" width="40" height="40" fill="%2316161a"><rect width="40" height="40"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="%238B7CF8" font-size="14">🎵</text></svg>';
                              }}
                            />
                            <div
                              style={{
                                position: 'absolute',
                                inset: 0,
                                backgroundColor: 'rgba(0, 0, 0, 0.45)',
                                display: 'flex',
                                alignItems: 'center',
                                justifyContent: 'center',
                                color: '#ffffff',
                                opacity: 0,
                                transition: 'opacity 150ms ease',
                              }}
                              className="play-overlay"
                            >
                              <Play size={14} fill="currentColor" />
                            </div>
                          </div>

                          <div style={{ minWidth: 0, flex: 1 }}>
                            <div
                              onClick={() => playSong(song, playlistSongs)}
                              style={{
                                fontWeight: 600,
                                color: '#f8fafc',
                                fontSize: '13.5px',
                                whiteSpace: 'nowrap',
                                overflow: 'hidden',
                                textOverflow: 'ellipsis',
                                cursor: 'pointer',
                              }}
                              title={song.title}
                            >
                              {song.title}
                            </div>
                            <div style={{ fontSize: '11.5px', color: 'var(--text-secondary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis', marginTop: '2px' }}>
                              {song.artist || 'Unknown Artist'}
                            </div>
                          </div>
                        </div>
                      </td>

                      <td style={{ color: 'var(--text-secondary)', fontSize: '12.5px' }}>
                        {song.album || '—'}
                      </td>
                      <td>
                        <DownloadStateBadge
                          state={song.state}
                          downloadState={isOwned ? 'DOWNLOADED' : 'NOT_DOWNLOADED'}
                        />
                      </td>
                      <td>
                        <QualityBadge quality={song.quality} isDownloaded={isOwned} />
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
                          {isOwned ? (
                            <button
                              onClick={() => handleOpenFolder(sId)}
                              className="btn-icon"
                              style={{ width: '28px', height: '28px', color: 'var(--color-success)' }}
                              title="Reveal file in Explorer"
                              aria-label="Reveal file"
                            >
                              <FolderOpen size={14} />
                            </button>
                          ) : (
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                downloadsApi.queueSongs([sId]).then(() => {
                                  showToast(`Queued "${song.title}" for download`, 'success');
                                  refreshStats();
                                });
                              }}
                              className="btn-icon"
                              style={{ width: '28px', height: '28px', color: 'var(--accent-primary)' }}
                              title="Download track"
                              aria-label="Download track"
                            >
                              <Download size={14} />
                            </button>
                          )}
                          <button
                            onClick={() => handleRemoveSong(sId, song.title)}
                            className="btn-icon"
                            style={{ width: '28px', height: '28px', color: 'var(--text-muted)' }}
                            title="Remove from playlist"
                            aria-label="Remove from playlist"
                          >
                            <X size={14} />
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
        </div>

        {/* Delete Confirmation Modal */}
        <Modal
          isOpen={deleteModalPlaylist !== null}
          onClose={() => setDeleteModalPlaylist(null)}
          title="Delete Playlist"
          subtitle={`Are you sure you want to delete "${deleteModalPlaylist?.name}"?`}
          footer={
            <>
              <Button variant="ghost" onClick={() => setDeleteModalPlaylist(null)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={confirmDeletePlaylist}
                style={{ backgroundColor: 'var(--color-error)', borderColor: 'var(--color-error)' }}
              >
                Delete Playlist
              </Button>
            </>
          }
        >
          <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
            This will remove the playlist collection. Your downloaded songs and library tracks will not be deleted.
          </div>
        </Modal>
      </div>
    );
  }

  return (
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Header Bar */}
      <div
        className="glass-panel"
        style={{
          padding: '20px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '36px',
              height: '36px',
              borderRadius: 'var(--radius-sm)',
              backgroundColor: 'rgba(251, 113, 133, 0.12)',
              border: '1px solid rgba(251, 113, 133, 0.22)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: '#FB7185',
            }}
          >
            <ListMusic size={20} />
          </div>
          <div>
            <h2 className="title-display" style={{ fontSize: '18px' }}>Custom Playlists</h2>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Curate and batch-download personal music collections
            </div>
          </div>
        </div>

        <Button variant="primary" onClick={() => setIsModalOpen(true)}>
          <Plus size={16} /> New Playlist
        </Button>
      </div>

      {/* Playlists Grid */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          Loading playlists...
        </div>
      ) : playlists.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
          No playlists created yet. Click "New Playlist" to create one!
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))',
            gap: '20px',
          }}
        >
          {playlists.map((pl) => (
            <Card
              key={pl.id}
              className="glass-card"
              onClick={() => handleOpenPlaylist(pl)}
              style={{ padding: '20px', display: 'flex', flexDirection: 'column', cursor: 'pointer' }}
            >
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '12px' }}>
                <div
                  style={{
                    width: '44px',
                    height: '44px',
                    borderRadius: 'var(--radius-md)',
                    background: 'linear-gradient(135deg, #1e1b4b 0%, #312e81 100%)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Music size={20} color="var(--accent-primary)" />
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setDeleteModalPlaylist(pl);
                  }}
                  className="btn-icon"
                  style={{ width: '32px', height: '32px', color: 'var(--text-muted)' }}
                  title="Delete playlist"
                  aria-label="Delete playlist"
                >
                  <Trash2 size={15} />
                </button>
              </div>

              <h4 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--text-primary)' }}>{pl.name}</h4>
              <p
                style={{
                  fontSize: '12px',
                  color: 'var(--text-muted)',
                  marginTop: '4px',
                  flex: 1,
                  lineHeight: 1.4,
                }}
              >
                {pl.description || 'No description provided.'}
              </p>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginTop: '16px',
                  paddingTop: '12px',
                  borderTop: '1px solid var(--border-subtle)',
                }}
              >
                <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>
                  {pl.song_count ?? 0} {pl.song_count === 1 ? 'song' : 'songs'}
                </span>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={(e) => handleDownload(e, pl.id, pl.name)}
                  aria-label={`Download all songs in ${pl.name}`}
                >
                  <Download size={13} /> Download All
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        title="Create New Playlist"
        subtitle="Organize custom mixes and download them in high quality"
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={handleCreate}>
              Create Playlist
            </Button>
          </>
        }
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Playlist Name
            </label>
            <input
              type="text"
              placeholder="e.g. Gym Workout Tamil Hits"
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-medium)',
                color: 'var(--text-primary)',
              }}
            />
          </div>

          <div>
            <label style={{ display: 'block', fontSize: '12px', fontWeight: 600, color: 'var(--text-secondary)', marginBottom: '6px' }}>
              Description (Optional)
            </label>
            <textarea
              placeholder="e.g. High energy tracks composed by Anirudh and Yuvan"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
              style={{
                width: '100%',
                padding: '10px 14px',
                borderRadius: 'var(--radius-md)',
                backgroundColor: 'var(--bg-surface)',
                border: '1px solid var(--border-medium)',
                color: 'var(--text-primary)',
                resize: 'none',
              }}
            />
          </div>
        </div>
      </Modal>

      {/* Delete Confirmation Modal */}
      <Modal
        isOpen={deleteModalPlaylist !== null}
        onClose={() => setDeleteModalPlaylist(null)}
        title="Delete Playlist"
        subtitle={`Are you sure you want to delete "${deleteModalPlaylist?.name}"?`}
        footer={
          <>
            <Button variant="ghost" onClick={() => setDeleteModalPlaylist(null)}>
              Cancel
            </Button>
            <Button
              variant="primary"
              onClick={confirmDeletePlaylist}
              style={{ backgroundColor: 'var(--color-error)', borderColor: 'var(--color-error)' }}
            >
              Delete Playlist
            </Button>
          </>
        }
      >
        <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>
          This will remove the playlist collection. Your downloaded songs and library tracks will not be deleted.
        </div>
      </Modal>
    </div>
  );
};
