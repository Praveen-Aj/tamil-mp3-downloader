import React, { useEffect, useState } from 'react';
import { Flame, Download, Play, RefreshCw, Music } from 'lucide-react';
import { chartsApi, downloadsApi } from '../../api/endpoints';
import { Chart, ChartEntry, Song } from '../../api/types';
import { Button } from '../common/Button';
import { Badge } from '../common/Badge';
import { useApp } from '../../context/AppContext';
import { useAudioPlayer } from '../../context/AudioPlayerContext';

export const ChartsView: React.FC = () => {
  const { showToast, refreshStats } = useApp();
  const { playSong } = useAudioPlayer();

  const [charts, setCharts] = useState<Chart[]>([]);
  const [selectedChartId, setSelectedChartId] = useState<string | null>(null);
  const [entries, setEntries] = useState<ChartEntry[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [downloadingChart, setDownloadingChart] = useState(false);

  useEffect(() => {
    const loadCharts = async () => {
      try {
        const res = await chartsApi.getCharts();
        const chartList = Array.isArray(res.data) ? res.data : ((res.data as any)?.charts || []);
        if (res.success && chartList.length > 0) {
          setCharts(chartList);
          if (!selectedChartId) {
            setSelectedChartId(chartList[0].id);
          }
        }
      } catch (err: any) {
        showToast(err.message || 'Failed to load charts', 'error');
      }
    };
    loadCharts();
  }, [showToast, selectedChartId]);

  useEffect(() => {
    if (!selectedChartId) return;
    const loadEntries = async () => {
      setLoading(true);
      try {
        const res = await chartsApi.getChart(selectedChartId);
        if (res.success && res.data) {
          setEntries(res.data.entries || []);
        }
      } catch (err: any) {
        showToast(err.message || 'Failed to load chart entries', 'error');
      } finally {
        setLoading(false);
      }
    };
    loadEntries();
  }, [selectedChartId, showToast]);

  const handleDownloadChart = async () => {
    if (!selectedChartId) return;
    setDownloadingChart(true);
    try {
      const res = await chartsApi.startDownload(selectedChartId);
      if (res.success) {
        showToast(`Queued ${res.data.queued_count} songs from chart`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue chart download', 'error');
    } finally {
      setDownloadingChart(false);
    }
  };

  const handleRefreshChart = async () => {
    if (!selectedChartId) return;
    setRefreshing(true);
    try {
      await chartsApi.refreshChart(selectedChartId);
      showToast('Chart refreshed from source', 'success');
      const res = await chartsApi.getChart(selectedChartId);
      if (res.success && res.data) {
        setEntries(res.data.entries || []);
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to refresh chart', 'error');
    } finally {
      setRefreshing(false);
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
      showToast(err.message || 'Failed to queue download', 'error');
    }
  };

  const handlePlaySong = (item: ChartEntry) => {
    const songObj: Song = {
      id: item.song_id || 0,
      title: item.title || item.raw_title,
      artist: item.artist || item.raw_artist,
      album: item.movie || item.raw_movie,
      state: 'OWNED',
      quality: item.quality_kbps || 320,
      has_file: true,
      is_favorite: false,
      file_path: item.file_path || undefined,
    };
    playSong(songObj);
  };

  const activeChart = charts.find((c) => c.id === selectedChartId);

  return (
    <div className="view-container" style={{ gap: '24px' }}>
      {/* Top Selector & Actions */}
      <div className="view-header">
        <div className="view-header-title">
          <div
            className="view-header-icon"
            style={{
              backgroundColor: 'rgba(244, 63, 94, 0.15)',
              borderColor: 'rgba(244, 63, 94, 0.25)',
              color: '#f43f5e',
            }}
          >
            <Flame size={20} />
          </div>
          <div>
            <h1 className="view-title">
              {activeChart?.name || activeChart?.title || 'Tamil Charts & Trends'}
            </h1>
            <div className="view-subtitle">
              {activeChart?.provider_name ? `${activeChart.provider_name} · ` : ''}{entries.length} tracks
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <Button variant="secondary" onClick={handleRefreshChart} loading={refreshing}>
            <RefreshCw size={15} /> Refresh
          </Button>
          {entries.length > 0 && (
            <Button variant="primary" onClick={handleDownloadChart} loading={downloadingChart}>
              <Download size={15} /> Download All
            </Button>
          )}
        </div>
      </div>

      {/* Chart Selector Pills */}
      <div style={{ display: 'flex', gap: '8px', overflowX: 'auto', paddingBottom: '4px' }}>
        {charts.map((c) => (
          <button
            key={c.id}
            onClick={() => setSelectedChartId(c.id)}
            className={`btn ${selectedChartId === c.id ? 'btn-primary' : 'btn-secondary'}`}
            style={{ padding: '8px 16px', borderRadius: 'var(--radius-pill)', fontSize: '13px' }}
          >
            {c.name || c.title}
          </button>
        ))}
      </div>

      {/* Chart Entries List */}
      <div className="table-card">
        {loading ? (
          <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
            Loading chart rankings...
          </div>
        ) : entries.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '56px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '14px' }}>
            <div style={{ width: '56px', height: '56px', borderRadius: '50%', backgroundColor: 'rgba(212, 163, 89, 0.12)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Flame size={28} color="var(--accent-primary)" />
            </div>
            <div>
              <h3 style={{ margin: '0 0 6px 0', fontSize: '17px', fontWeight: 700, color: 'var(--text-primary)' }}>
                Tamil Top Charts & Trends
              </h3>
              <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: '13.5px', maxWidth: '420px', lineHeight: 1.5 }}>
                Charts compile the most popular Tamil cinema songs and weekly viral streams. Connect provider feeds or refresh to fetch the latest ranking snapshot.
              </p>
            </div>
            <Button variant="secondary" onClick={handleRefreshChart} loading={refreshing} style={{ marginTop: '6px', fontSize: '13px' }}>
              <RefreshCw size={14} /> Fetch Latest Charts
            </Button>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '70px', textAlign: 'center' }}>Rank</th>
                <th style={{ width: '70px', textAlign: 'center' }}>Trend</th>
                <th>Track Title & Artists</th>
                <th>Film / Album</th>
                <th style={{ width: '130px', textAlign: 'center' }}>Status</th>
                <th style={{ width: '130px', textAlign: 'right', paddingRight: '20px' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((item) => {
                const isOwned = Boolean(item.is_downloaded || item.is_owned);
                const title = item.title || item.raw_title;
                const artist = item.artist || item.raw_artist;
                const movie = item.movie || item.raw_movie;

                return (
                  <tr key={`${item.chart_id}-${item.rank}`}>
                    <td style={{ textAlign: 'center', fontWeight: 800, fontSize: '14px' }}>
                      <span
                        style={{
                          color:
                            item.rank === 1
                              ? '#f59e0b'
                              : item.rank === 2
                              ? '#94a3b8'
                              : item.rank === 3
                              ? '#d97706'
                              : 'var(--text-muted)',
                        }}
                      >
                        #{item.rank}
                      </span>
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      {item.trend === 'up' && (
                        <span style={{ color: '#10b981', fontSize: '12px', fontWeight: 700 }}>
                          {item.trend_label || '▲'}
                        </span>
                      )}
                      {item.trend === 'down' && (
                        <span style={{ color: '#ef4444', fontSize: '12px', fontWeight: 700 }}>
                          {item.trend_label || '▼'}
                        </span>
                      )}
                      {item.trend === 'new' && (
                        <span style={{ color: 'var(--accent-primary)', fontSize: '11px', fontWeight: 700 }}>
                          NEW
                        </span>
                      )}
                      {(item.trend === 'same' || !item.trend) && (
                        <span style={{ color: 'var(--text-muted)', fontSize: '12px' }}>＝</span>
                      )}
                    </td>
                    <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <Music size={14} color="var(--accent-primary)" />
                        <div>
                          <div>{title}</div>
                          {artist && (
                            <div style={{ fontSize: '12px', color: 'var(--text-secondary)', fontWeight: 400 }}>
                              {artist}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>
                    <td style={{ color: 'var(--text-secondary)', fontSize: '13px' }}>
                      {movie || '-'}
                    </td>
                    <td style={{ textAlign: 'center' }}>
                      <Badge variant={isOwned ? 'success' : 'subtle'}>
                        {isOwned ? '✓ In Library' : 'Available'}
                      </Badge>
                    </td>
                    <td style={{ textAlign: 'right', paddingRight: '20px' }}>
                      {isOwned ? (
                        <button
                          className="btn btn-secondary"
                          style={{ padding: '6px 12px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                          onClick={() => handlePlaySong(item)}
                        >
                          <Play size={12} fill="currentColor" /> Play
                        </button>
                      ) : item.song_id ? (
                        <button
                          className="btn btn-secondary"
                          style={{ padding: '6px 12px', fontSize: '12px', display: 'inline-flex', alignItems: 'center', gap: '6px' }}
                          onClick={() => handleDownloadSong(item.song_id!)}
                        >
                          <Download size={12} /> Download
                        </button>
                      ) : (
                        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>-</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
