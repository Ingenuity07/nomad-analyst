import React, { useEffect, useRef, useState } from 'react';
import { createChart, IChartApi, ISeriesApi, CandlestickData, HistogramData, Time } from 'lightweight-charts';
import { Card } from '@/components/ui/Card';
import { Skeleton } from '@/components/ui/Skeleton';
import { useStockOHLCV } from '@/hooks/useStockOHLCV';

export interface StockChartCardProps {
  symbol: string;
}

const TIMEFRAME_OPTIONS = [
  { label: '5m', value: '5m', limit: 150 },
  { label: '15m', value: '15m', limit: 150 },
  { label: '1h', value: '1h', limit: 200 },
  { label: '1D', value: '1d', limit: 250 },
  { label: '1M', value: '1d', limit: 30 },
  { label: '1Y', value: '1d', limit: 250 },
  { label: '5Y', value: '1d', limit: 1000 },
];

export const StockChartCard: React.FC<StockChartCardProps> = ({ symbol }) => {
  const [selectedTf, setSelectedTf] = useState<string>('1d');
  const [hoveredBar, setHoveredBar] = useState<any | null>(null);

  const activeOption = TIMEFRAME_OPTIONS.find((o) => o.value === selectedTf) || TIMEFRAME_OPTIONS[3];

  const { data: ohlcvData, isLoading, error } = useStockOHLCV(symbol, selectedTf, activeOption.limit);

  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null);

  useEffect(() => {
    if (!chartContainerRef.current) return;

    // Create chart
    const chart = createChart(chartContainerRef.current, {
      width: chartContainerRef.current.clientWidth,
      height: 380,
      layout: {
        background: { color: '#0F172A' },
        textColor: '#94A3B8',
        fontSize: 11,
        fontFamily: 'JetBrains Mono, monospace',
      },
      grid: {
        vertLines: { color: 'rgba(30, 41, 59, 0.6)' },
        horzLines: { color: 'rgba(30, 41, 59, 0.6)' },
      },
      crosshair: {
        mode: 1,
        vertLine: { color: '#38BDF8', width: 1, style: 3 },
        horzLine: { color: '#38BDF8', width: 1, style: 3 },
      },
      timeScale: {
        borderColor: '#1E293B',
        timeVisible: selectedTf !== '1d',
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#1E293B',
        scaleMargins: { top: 0.1, bottom: 0.25 },
      },
    });

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#10B981',
      downColor: '#EF4444',
      borderVisible: false,
      wickUpColor: '#10B981',
      wickDownColor: '#EF4444',
    });

    const volumeSeries = chart.addHistogramSeries({
      color: '#38BDF8',
      priceFormat: { type: 'volume' },
      priceScaleId: '', // Overlay on separate margin
    });

    volumeSeries.priceScale().applyOptions({
      scaleMargins: { top: 0.8, bottom: 0 },
    });

    chartRef.current = chart;
    candleSeriesRef.current = candleSeries;
    volumeSeriesRef.current = volumeSeries;

    // Crosshair hover subscribe
    chart.subscribeCrosshairMove((param) => {
      if (!param || !param.time || !param.seriesData) {
        setHoveredBar(null);
        return;
      }
      const candleData = param.seriesData.get(candleSeries) as CandlestickData;
      const volData = param.seriesData.get(volumeSeries) as HistogramData;
      if (candleData) {
        setHoveredBar({
          time: param.time,
          open: candleData.open,
          high: candleData.high,
          low: candleData.low,
          close: candleData.close,
          volume: volData?.value ?? null,
        });
      }
    });

    // Resize observer
    const handleResize = () => {
      if (chartContainerRef.current && chartRef.current) {
        chartRef.current.applyOptions({ width: chartContainerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
    };
  }, [selectedTf]);

  // Update data when query completes
  useEffect(() => {
    if (!ohlcvData || !ohlcvData.bars || !candleSeriesRef.current || !volumeSeriesRef.current) return;

    const rawBars = ohlcvData.bars;
    const candles: CandlestickData[] = [];
    const volumes: HistogramData[] = [];

    rawBars.forEach((b) => {
      // Format time: if 1d, 'YYYY-MM-DD'; else unix timestamp in seconds
      const dt = new Date(b.timestamp);
      const timeVal = (selectedTf === '1d'
        ? dt.toISOString().split('T')[0]
        : Math.floor(dt.getTime() / 1000)) as Time;

      const open = Number(b.open);
      const high = Number(b.high);
      const low = Number(b.low);
      const close = Number(b.close);
      const vol = Number(b.volume);

      candles.push({ time: timeVal, open, high, low, close });
      volumes.push({
        time: timeVal,
        value: vol,
        color: close >= open ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)',
      });
    });

    // Sort chronologically ascending
    candles.sort((a, b) => (String(a.time) > String(b.time) ? 1 : -1));
    volumes.sort((a, b) => (String(a.time) > String(b.time) ? 1 : -1));

    candleSeriesRef.current.setData(candles);
    volumeSeriesRef.current.setData(volumes);

    if (chartRef.current) {
      chartRef.current.timeScale().fitContent();
    }
  }, [ohlcvData, selectedTf]);

  return (
    <Card>
      {/* Chart Top Bar: Timeframe buttons & OHLC bar values */}
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 'var(--space-3)',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: 'var(--space-3)',
          marginBottom: 'var(--space-3)',
        }}
      >
        {/* Timeframe Buttons */}
        <div style={{ display: 'flex', gap: 'var(--space-1)' }}>
          {TIMEFRAME_OPTIONS.map((opt) => (
            <button
              key={opt.label}
              onClick={() => setSelectedTf(opt.value)}
              style={{
                fontSize: 'var(--text-xs)',
                fontWeight: selectedTf === opt.value ? 'var(--weight-bold)' : 'var(--weight-medium)',
                fontFamily: 'var(--font-mono)',
                padding: 'var(--space-1) var(--space-2-5)',
                borderRadius: 'var(--radius-xs)',
                backgroundColor: selectedTf === opt.value ? 'var(--brand-primary)' : 'var(--bg-surface-elevated)',
                color: selectedTf === opt.value ? '#FFFFFF' : 'var(--text-secondary)',
                border: '1px solid var(--border-subtle)',
                cursor: 'pointer',
              }}
            >
              {opt.label}
            </button>
          ))}
        </div>

        {/* OHLCV Crosshair Values */}
        {hoveredBar ? (
          <div
            style={{
              fontSize: 'var(--text-2xs)',
              fontFamily: 'var(--font-mono)',
              display: 'flex',
              gap: 'var(--space-3)',
              color: 'var(--text-secondary)',
            }}
          >
            <span>O: <strong style={{ color: 'var(--text-primary)' }}>₹{hoveredBar.open?.toFixed(2)}</strong></span>
            <span>H: <strong style={{ color: 'var(--positive)' }}>₹{hoveredBar.high?.toFixed(2)}</strong></span>
            <span>L: <strong style={{ color: 'var(--negative)' }}>₹{hoveredBar.low?.toFixed(2)}</strong></span>
            <span>C: <strong style={{ color: 'var(--text-primary)' }}>₹{hoveredBar.close?.toFixed(2)}</strong></span>
            {hoveredBar.volume && <span>Vol: <strong style={{ color: 'var(--text-primary)' }}>{(hoveredBar.volume / 1e5).toFixed(2)}L</strong></span>}
          </div>
        ) : (
          <div style={{ fontSize: 'var(--text-2xs)', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            Hover over bars to inspect OHLCV
          </div>
        )}
      </div>

      {/* Chart Canvas Container */}
      {isLoading ? (
        <Skeleton height="380px" />
      ) : error ? (
        <div style={{ height: '380px', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'var(--text-muted)' }}>
          Historical chart data unavailable for this timeframe.
        </div>
      ) : (
        <div ref={chartContainerRef} style={{ width: '100%', height: '380px', borderRadius: 'var(--radius-sm)', overflow: 'hidden' }} />
      )}
    </Card>
  );
};
