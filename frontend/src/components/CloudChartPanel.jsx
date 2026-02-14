import { useMemo, useState, useCallback } from 'react'
import {
  ComposedChart, Bar, Cell, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { interpolateGaps, addTrendLine, dailyTicks, dailyTickFormatter, yearlyTicks } from '../utils/chartHelpers'

const BAR_FILL = 'rgba(100, 126, 234, 0.65)'
const BAR_EST_FILL = 'rgba(100, 126, 234, 0.25)'
const BAR_EST_STROKE = 'rgba(100, 126, 234, 0.45)'
const CLOUD_STROKE = 'rgba(100, 126, 234, 0.9)'
const TREND_STROKE = 'rgba(100, 126, 234, 0.5)'

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
    return addTrendLine(interp, isDaily ? 0.08 : isYearly ? 0.25 : 0.35)
  }, [data.points, isDaily, isYearly])

  const showTrend = chartData.some((p) => p.trend_cloud != null)
  const hasEstimated = chartData.some((p) => p.interpolated)

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
            <span className="legend-est" aria-label="Faded bars are estimated">
              <span className="legend-bar-swatch legend-bar-est" />
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
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.08)" />
          <XAxis
            dataKey="label"
            tick={{ fill: '#aaa', fontSize: compact ? 10 : (isDaily ? 11 : 13) }}
            ticks={isYearly ? yearlyTicks(chartData) : isDaily ? dailyTicks(chartData) : undefined}
            interval={isDaily ? 0 : 0}
            tickFormatter={isDaily ? dailyTickFormatter : undefined}
            angle={isYearly ? -45 : 0}
            textAnchor={isYearly ? 'end' : 'middle'}
            height={isYearly ? 45 : 25}
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

          <Bar
            dataKey="cloud_coverage_avg"
            name="Cloud coverage"
            isAnimationActive={false}
            radius={isDaily ? 0 : [2, 2, 0, 0]}
          >
            {chartData.map((p, i) => (
              <Cell
                key={i}
                fill={p.interpolated ? BAR_EST_FILL : BAR_FILL}
                stroke={p.interpolated ? BAR_EST_STROKE : 'none'}
                strokeWidth={p.interpolated ? 1 : 0}
                strokeDasharray={p.interpolated ? '3 2' : undefined}
              />
            ))}
          </Bar>

          {showTrend && (
            <Line
              type="monotone"
              dataKey="trend_cloud"
              stroke={TREND_STROKE}
              strokeWidth={2}
              strokeDasharray="4 3"
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
