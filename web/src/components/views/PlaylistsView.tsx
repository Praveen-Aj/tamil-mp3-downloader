import React, { useEffect, useState, useCallback } from 'react';
import { ListMusic, Plus, Download, Trash2, Music } from 'lucide-react';
import { playlistsApi } from '../../api/endpoints';
import { Playlist } from '../../api/types';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import { Modal } from '../common/Modal';
import { useApp } from '../../context/AppContext';

export const PlaylistsView: React.FC = () => {
  const { showToast, refreshStats } = useApp();
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [loading, setLoading] = useState(false);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');

  const loadPlaylists = useCallback(async () => {
    setLoading(true);
    try {
      const res = await playlistsApi.getPlaylists();
      if (res.success && res.data) {
        setPlaylists(res.data.items || []);
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

  const handleDelete = async (e: React.MouseEvent, plId: number) => {
    e.stopPropagation();
    if (!window.confirm('Delete this playlist?')) return;
    try {
      await playlistsApi.deletePlaylist(plId);
      showToast('Playlist deleted', 'info');
      refreshStats();
      loadPlaylists();
    } catch (err: any) {
      showToast(err.message || 'Failed to delete playlist', 'error');
    }
  };

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
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              backgroundColor: 'rgba(99, 102, 241, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <ListMusic size={22} color="var(--accent-primary)" />
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
            <Card key={pl.id} className="glass-card" style={{ padding: '20px', display: 'flex', flexDirection: 'column' }}>
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
                  onClick={(e) => handleDelete(e, pl.id)}
                  className="btn-icon"
                  style={{ width: '32px', height: '32px', color: 'var(--text-muted)' }}
                  title="Delete playlist"
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
                  {pl.song_count ?? 0} songs
                </span>
                <Button size="sm" variant="secondary" onClick={(e) => handleDownload(e, pl.id, pl.name)}>
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
    </div>
  );
};
