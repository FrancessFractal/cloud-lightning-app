import { useMemo, useState, useCallback } from 'react'
import {
  ComposedChart, Area, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer,
} from 'recharts'
import { interpolateGaps, dailyTicks, dailyTickFormatter, fmtLightning, yearlyTicks } from '../utils/chartHelpers'

const LIGHTNING_STROKE = '#f5a623'
const BAND_FILL = 'rgba(245, 166, 35, 0.18)'

export default function LightningChartPanel({
  data,
  resolution,
  height = 260,
  compact = false,
  activeLabel,
  onHover,
}) {
  if (!data.has_lightning_data) return null

  const isDaily = resolution === 'day'
  const isYearly = resolution === 'year'

  const interpolated = useMemo(
    () => interpolateGaps(data.points, ['lightning_probability']),
    [data.points],
  )

  // Compute a ci_band field (upper − lower) so we can render a proper
  // stacked area band without hardcoding a background colour.
  const chartData = useMemo(
    () =>
      interpolated.map((p) => ({
        ...p,
        ci_band:
          p.lightning_lower != null && p.lightning_upper != null
            ? p.lightning_upper - p.lightning_lower
            : null,
      })),
    [interpolated],
  )

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

    const prob = point?.lightning_probability
    const lower = point?.lightning_lower
    const upper = point?.lightning_upper

    return (
      <div className="custom-tooltip">
        <p className="tooltip-label">{label}</p>
        <p className="tooltip-row" style={{ color: LIGHTNING_STROKE }}>
          Lightning: {fmtLightning(prob)}
        </p>
        {lower != null && upper != null && (
          <p className="tooltip-row tooltip-ci">
            Confidence interval: {fmtLightning(lower)} – {fmtLightning(upper)}
          </p>
        )}
        <p className="tooltip-row tooltip-type">
          Data type: {isEst ? 'Estimated' : 'Measured'}
        </p>
      </div>
    )
  }

  // Check if we have confidence band data
  const hasBands = chartData.some(
    (p) => p.lightning_lower != null && p.lightning_upper != null
  )

  return (
    <div
      className="chart-panel"
      role="img"
      aria-label={`Lightning probability chart. ${chartData.length} data points. Use left and right arrow keys to navigate.`}
      tabIndex={0}
      onKeyDown={handleKeyDown}
    >
      {!compact && <h3 className="panel-title">Lightning Probability (%)</h3>}
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
            domain={[0, 'auto']}
            tick={{ fill: '#aaa', fontSize: compact ? 10 : 13 }}
            width={40}
            label={compact ? undefined : {
              value: 'Lightning %',
              angle: -90,
              position: 'insideLeft',
              style: { fill: '#aaa', fontSize: 11 },
            }}
          />
          <Tooltip content={renderTooltip} />

          {/* Confidence band — stacked: invisible base + visible gap */}
          {hasBands && (
            <Area
              type="monotone"
              dataKey="lightning_lower"
              stackId="ci"
              stroke="none"
              fill="transparent"
              dot={false}
              connectNulls
              name="Lower bound"
              legendType="none"
              isAnimationActive={false}
            />
          )}
          {hasBands && (
            <Area
              type="monotone"
              dataKey="ci_band"
              stackId="ci"
              stroke="none"
              fill={BAND_FILL}
              fillOpacity={1}
              dot={false}
              connectNulls
              name="Confidence band"
              legendType="none"
              isAnimationActive={false}
            />
          )}

          {/* Main probability line */}
          <Line
            type="monotone"
            dataKey="lightning_probability"
            stroke={LIGHTNING_STROKE}
            strokeWidth={isDaily ? 1.5 : 2}
            dot={isDaily || compact ? false : { r: 3, fill: LIGHTNING_STROKE }}
            connectNulls
            name="Lightning probability"
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
