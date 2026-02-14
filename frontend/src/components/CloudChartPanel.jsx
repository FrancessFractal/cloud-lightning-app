import { useMemo, useState, useCallback } from 'react'
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { interpolateGaps, addTrendLine, dailyTickFormatter } from '../utils/chartHelpers'

const CLOUD_FILL = 'rgba(100, 126, 234, 0.45)'
const CLOUD_STROKE = 'rgba(100, 126, 234, 0.9)'
const EST_FILL = 'url(#estHatch)'
const EST_STROKE = 'rgba(100, 126, 234, 0.4)'
const TREND_STROKE = 'rgba(100, 126, 234, 0.45)'

export default function CloudChartPanel({
  data,
  resolution,
  height = 260,
  compact = false,
  activeLabel,
  onHover,
}) {
  const isDaily = resolution === 'day'
  const isYearly = resolution === 'year'

  const chartData = useMemo(() => {
    const interp = interpolateGaps(data.points, ['cloud_coverage_avg'])
    const withTrend = isYearly ? addTrendLine(interp) : interp

    // Split into measured vs estimated series for hatched overlay
    return withTrend.map((p) => ({
      ...p,
      cloud_measured: p.interpolated ? null : p.cloud_coverage_avg,
      cloud_estimated: p.interpolated ? p.cloud_coverage_avg : null,
    }))
  }, [data.points, isYearly])

  const showTrend = isYearly && chartData.some((p) => p.trend_cloud != null)
  const hasEstimated = chartData.some((p) => p.cloud_estimated != null)

  const [focusIdx, setFocusIdx] = useState(null)

  const handleMouseMove = (state) => {
    if (onHover && state?.activeLabel) onHover(state.activeLabel)
  }
  const handleMouseLeave = () => { if (onHover) onHover(null) }

  const handleKeyDown = useCallback((e) => {
    if (!chartData.length) return
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault()
      setFocusIdx((prev) => {
        const cur = prev ?? -1
        const next = e.key === 'ArrowRight'
          ? Math.min(cur + 1, chartData.length - 1)
          : Math.max(cur - 1, 0)
        if (onHover) onHover(chartData[next]?.label)
        return next
      })
    } else if (e.key === 'Escape') {
      setFocusIdx(null)
      if (onHover) onHover(null)
    }
  }, [chartData, onHover])

  const renderTooltip = ({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) return null
    const point = chartData.find((p) => p.label === label)
    const isEst = point?.interpolated
    const cloudVal = point?.cloud_coverage_avg
    return (
      <div className="custom-tooltip">
        <p className="tooltip-label">{label}</p>
        <p className="tooltip-row" style={{ color: CLOUD_STROKE }}>
          Cloud coverage: {cloudVal != null ? `${cloudVal}%` : 'N/A'}
        </p>
        <p className="tooltip-row tooltip-type">
          Data type: {isEst ? 'Estimated' : 'Measured'}
        </p>
      </div>
    )
  }

  return (
    <div
      className="chart-panel"
      role="img"
      aria-label={`Cloud coverage chart. ${chartData.length} data points. Use left and right arrow keys to navigate.`}
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      {!compact && (
        <div className="panel-header">
          <h3 className="panel-title">Cloud Coverage (%)</h3>
          {hasEstimated && (
            <span className="legend-est" aria-label="Hatched areas are estimated">
              <svg width="14" height="14" className="legend-swatch">
                <defs>
                  <pattern id="legendHatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
                    <line x1="0" y1="0" x2="0" y2="4" stroke="rgba(100,126,234,0.55)" strokeWidth="2" />
                  </pattern>
                </defs>
                <rect width="14" height="14" fill="url(#legendHatch)" rx="2" />
              </svg>
              <span className="legend-est-text">Estimated</span>
            </span>
          )}
        </div>
      )}
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={chartData}
          margin={{ top: 5, right: 15, left: 0, bottom: 0 }}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
        >
          <defs>
            <pattern
              id="estHatch"
              width="6"
              height="6"
              patternUnits="userSpaceOnUse"
              patternTransform="rotate(45)"
            >
              <rect width="6" height="6" fill="rgba(100,126,234,0.12)" />
              <line x1="0" y1="0" x2="0" y2="6" stroke="rgba(100,126,234,0.35)" strokeWidth="2" />
            </pattern>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
          <XAxis
            dataKey="label"
            tick={{ fill: '#aaa', fontSize: compact ? 10 : (isDaily ? 11 : 13) }}
            interval={isDaily ? 'preserveStartEnd' : 0}
            tickFormatter={isDaily ? dailyTickFormatter : undefined}
            angle={isYearly ? -45 : 0}
            textAnchor={isYearly ? 'end' : 'middle'}
            height={isYearly ? 50 : 25}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: '#aaa', fontSize: compact ? 10 : 13 }}
            width={40}
            label={compact ? undefined : {
              value: 'Cloud %',
              angle: -90,
              position: 'insideLeft',
              style: { fill: '#aaa', fontSize: 11 },
            }}
          />
          <Tooltip content={renderTooltip} />

          {/* Measured data: solid fill */}
          <Area
            type="monotone"
            dataKey="cloud_measured"
            stroke={CLOUD_STROKE}
            strokeWidth={1.5}
            fill={CLOUD_FILL}
            fillOpacity={1}
            dot={false}
            connectNulls={false}
            name="Measured"
            isAnimationActive={false}
            legendType="none"
          />

          {/* Full connected line (both measured + estimated) */}
          <Area
            type="monotone"
            dataKey="cloud_coverage_avg"
            stroke={CLOUD_STROKE}
            strokeWidth={1}
            fill="none"
            dot={false}
            connectNulls
            name="Cloud coverage"
            isAnimationActive={false}
            legendType="none"
          />

          {/* Estimated data: hatched pattern fill */}
          <Area
            type="monotone"
            dataKey="cloud_estimated"
            stroke={EST_STROKE}
            strokeWidth={1}
            strokeDasharray="4 3"
            fill={EST_FILL}
            fillOpacity={1}
            dot={false}
            connectNulls={false}
            name="Estimated"
            isAnimationActive={false}
            legendType="none"
          />

          {showTrend && (
            <Line
              type="monotone"
              dataKey="trend_cloud"
              stroke={TREND_STROKE}
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={false}
              name="Trend"
              isAnimationActive={false}
              connectNulls
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
