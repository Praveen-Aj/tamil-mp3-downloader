import React, { useEffect, useState } from 'react';
import { Flame, Download, Play, RefreshCw, Music } from 'lucide-react';
import { chartsApi } from '../../api/endpoints';
import { Chart, ChartEntry } from '../../api/types';
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

  useEffect(() => {
    const loadCharts = async () => {
      try {
        const res = await chartsApi.getCharts();
        if (res.success && res.data?.charts) {
          setCharts(res.data.charts);
          if (res.data.charts.length > 0 && !selectedChartId) {
            setSelectedChartId(res.data.charts[0].id);
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
    try {
      const res = await chartsApi.startDownload(selectedChartId);
      if (res.success) {
        showToast(`Queued ${res.data.queued_count} songs from chart`, 'success');
        refreshStats();
      }
    } catch (err: any) {
      showToast(err.message || 'Failed to queue chart download', 'error');
    }
  };

  const handleRefreshChart = async () => {
    if (!selectedChartId) return;
    setRefreshing(true);
    try {
      await chartsApi.refreshChart(selectedChartId);
      showToast('Chart refreshed from remote source', 'success');
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

  const activeChart = charts.find((c) => c.id === selectedChartId);

  return (
    <div style={{ padding: '32px', display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Top Selector & Actions */}
      <div
        className="glass-panel"
        style={{
          padding: '20px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <div
            style={{
              width: '40px',
              height: '40px',
              borderRadius: '10px',
              backgroundColor: 'rgba(244, 63, 94, 0.15)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <Flame size={22} color="#f43f5e" />
          </div>
          <div>
            <h2 className="title-display" style={{ fontSize: '18px' }}>
              {activeChart?.title || 'Trending Charts'}
            </h2>
            <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Provider: {activeChart?.provider_name || 'Regional'} • {entries.length} tracks
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '10px' }}>
          <Button variant="secondary" onClick={handleRefreshChart} loading={refreshing}>
            <RefreshCw size={15} /> Refresh
          </Button>
          <Button variant="primary" onClick={handleDownloadChart}>
            <Download size={15} /> Download All
          </Button>
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
            {c.title}
          </button>
        ))}
      </div>

      {/* Chart Entries List */}
      <div className="glass-panel" style={{ padding: '8px 0', overflow: 'hidden' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
            Loading chart entries...
          </div>
        ) : entries.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '48px', color: 'var(--text-muted)' }}>
            No entries found in this chart.
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th style={{ width: '60px', textAlign: 'center' }}>Rank</th>
                <th>Track Title</th>
                <th style={{ width: '120px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((item) => (
                <tr key={`${item.chart_id}-${item.rank}`}>
                  <td style={{ textAlign: 'center', fontWeight: 800, fontSize: '15px' }}>
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
                  <td style={{ fontWeight: 600, color: 'var(--text-primary)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <Music size={14} color="var(--accent-primary)" />
                      <span>{item.raw_title}</span>
                    </div>
                  </td>
                  <td>
                    <Badge variant={item.is_owned ? 'success' : 'primary'}>
                      {item.is_owned ? 'In Library' : 'Available'}
                    </Badge>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
};
