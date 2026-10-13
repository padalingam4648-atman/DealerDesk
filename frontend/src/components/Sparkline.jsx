import React, { useMemo } from 'react';

/**
 * Hand-written inline SVG Sparkline for 4-week demand forecast
 * No external chart libraries. Pure SVG path and coordinates.
 */
export default function Sparkline({
  data = [],
  width = 90,
  height = 24,
  stroke = 'var(--accent)',
  strokeWidth = 1.5,
}) {
  // Extract numerical values
  const points = useMemo(() => {
    if (!Array.isArray(data) || data.length === 0) return [];
    return data.map(item => {
      if (typeof item === 'number') return item;
      if (item && typeof item.forecast_units === 'number') return item.forecast_units;
      if (item && item.forecast_units) return parseFloat(item.forecast_units) || 0;
      return 0;
    });
  }, [data]);

  if (points.length < 2) {
    return <span className="text-muted text-xs">—</span>;
  }

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min === 0 ? 1 : max - min;
  const padding = 3;

  const innerWidth = width - padding * 2;
  const innerHeight = height - padding * 2;

  const coords = points.map((val, idx) => {
    const x = padding + (idx / (points.length - 1)) * innerWidth;
    // Invert y since SVG (0,0) is top-left
    const y = padding + innerHeight - ((val - min) / range) * innerHeight;
    return { x, y, val };
  });

  const polylinePoints = coords.map(c => `${c.x.toFixed(1)},${c.y.toFixed(1)}`).join(' ');

  return (
    <svg
      className="sparkline-svg"
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      role="img"
      aria-label={`Demand trend: ${points.join(', ')}`}
    >
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        points={polylinePoints}
      />
      {coords.map((c, i) => (
        <circle
          key={i}
          cx={c.x}
          cy={c.y}
          r={i === coords.length - 1 ? 2.5 : 1.8}
          fill={i === coords.length - 1 ? stroke : 'var(--bg-surface)'}
          stroke={stroke}
          strokeWidth={1}
        />
      ))}
    </svg>
  );
}
