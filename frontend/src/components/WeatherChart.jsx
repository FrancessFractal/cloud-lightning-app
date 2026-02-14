import { useMemo } from 'react'
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
} from 'recharts'

const RESOLUTIONS = [
  { key: 'day', label: 'Day' },
  { key: 'month', label: 'Month' },
  { key: 'year', label: 'Year' },
]

const CLOUD_FILL = 'rgba(100, 126, 234, 0.7)'
const CLOUD_FILL_FADED = 'rgba(100, 126, 234, 0.22)'
const CLOUD_STROKE = 'rgba(100, 126, 234, 0.9)'
const CLOUD_STROKE_FADED = 'rgba(100, 126, 234, 0.35)'
const LIGHTNING_STROKE = '#f5a623'

/**
 * Fill null gaps in an array by linearly interpolating between the nearest
 * non-null neighbours.  Returns a new array with `interpolated: true` on
 * filled-in points.
 */
function interpolateGaps(points) {
  const result = points.map((p) => ({ ...p }))

  const fields = ['cloud_coverage_avg', 'lightning_probability']
  for (const field of fields) {
    let i = 0
    while (i < result.length) {
      if (result[i][field] != null) {
        i++
        continue
      }

      // Find start of gap (index of last real value before gap)
      const gapStart = i - 1
      // Find end of gap (index of next real value after gap)
      let gapEnd = i
      while (gapEnd < result.length && result[gapEnd][field] == null) {
        gapEnd++
      }

      const leftVal = gapStart >= 0 ? result[gapStart][field] : null
      const rightVal = gapEnd < result.length ? result[gapEnd][field] : null

      if (leftVal != null && rightVal != null) {
        // Interpolate between the two
        const span = gapEnd - gapStart
        for (let j = gapStart + 1; j < gapEnd; j++) {
          const t = (j - gapStart) / span
          result[j][field] = Math.round((leftVal + (rightVal - leftVal) * t) * 10) / 10
          result[j].interpolated = true
        }
      } else if (leftVal != null) {
        // Extend flat from left
        for (let j = gapStart + 1; j < gapEnd; j++) {
          result[j][field] = leftVal
          result[j].interpolated = true
        }
      } else if (rightVal != null) {
        // Extend flat from right
        for (let j = i; j < gapEnd; j++) {
          result[j][field] = rightVal
          result[j].interpolated = true
        }
      }

      i = gapEnd
    }
  }

  return result
}

export default function WeatherChart({ data, locationName, resolution, onResolutionChange }) {
  if (!data || !data.points || data.points.length === 0) return null

  const hasLightning = data.has_lightning_data
  const stations = data.stations || []
  const isDaily = resolution === 'day'

  const chartData = useMemo(() => interpolateGaps(data.points), [data.points])
  const hasInterpolated = useMemo(
    () => chartData.some((p) => p.interpolated),
    [chartData],
  )

  // Shorten location to city/region (first two comma-separated parts)
  const shortLocation = locationName
    ? locationName.split(',').slice(0, 2).join(',').trim()
    : null

  // For daily view (366 points), only show month labels as tick marks
  const dailyTickFormatter = (label) => {
    if (label.endsWith(' 01')) return label.replace(/ 01$/, '')
    return ''
  }

  // Custom tooltip that tags interpolated values
  const renderTooltip = ({ active, payload, label }) => {
    if (!active || !payload || payload.length === 0) return null
    const point = chartData.find((p) => p.label === label)
    const isEst = point?.interpolated

    return (
      <div className="custom-tooltip">
        <p className="tooltip-label">{label}{isEst ? '  (estimated)' : ''}</p>
        {payload.map((entry) => (
          <p key={entry.name} style={{ color: entry.color }} className="tooltip-row">
            {entry.name}: {entry.value != null ? `${entry.value}%` : 'N/A'}
          </p>
        ))}
        {isEst && (
          <p className="tooltip-est-note">No observations — interpolated from neighbours</p>
        )}
      </div>
    )
  }

  return (
    <div className="card chart-card">
      <div className="chart-header">
        <div>
          <h2>Climate estimate{shortLocation ? ` — ${shortLocation}` : ''}</h2>
          <p className="hint">
            Weighted blend of {stations.length} nearby SMHI station{stations.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div className="resolution-toggle">
          {RESOLUTIONS.map((r) => (
            <button
              key={r.key}
              className={`res-btn ${resolution === r.key ? 'active' : ''}`}
              onClick={() => onResolutionChange(r.key)}
            >
              {r.label}
            </button>
          ))}
        </div>
      </div>

      {!hasLightning && (
        <p className="notice">
          None of the nearby stations record present weather observations, so
          lightning data is not available.
        </p>
      )}

      {hasInterpolated && (
        <p className="notice interpolation-notice">
          <span className="faded-swatch" /> Faded bars indicate periods with no
          station data — values are estimated by interpolation.
        </p>
      )}

      <ResponsiveContainer width="100%" height={380}>
        <ComposedChart
          data={chartData}
          margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
          <XAxis
            dataKey="label"
            tick={{ fill: '#aaa', fontSize: isDaily ? 11 : 13 }}
            interval={isDaily ? 'preserveStartEnd' : 0}
            tickFormatter={isDaily ? dailyTickFormatter : undefined}
            angle={resolution === 'year' ? -45 : 0}
            textAnchor={resolution === 'year' ? 'end' : 'middle'}
            height={resolution === 'year' ? 60 : 30}
          />
          <YAxis
            yAxisId="cloud"
            domain={[0, 100]}
            tick={{ fill: '#aaa', fontSize: 13 }}
            label={{
              value: 'Cloud coverage %',
              angle: -90,
              position: 'insideLeft',
              style: { fill: '#aaa', fontSize: 12 },
            }}
          />
          {hasLightning && (
            <YAxis
              yAxisId="lightning"
              orientation="right"
              domain={[0, 'auto']}
              tick={{ fill: '#aaa', fontSize: 13 }}
              label={{
                value: 'Lightning prob. %',
                angle: 90,
                position: 'insideRight',
                style: { fill: '#aaa', fontSize: 12 },
              }}
            />
          )}
          <Tooltip content={renderTooltip} />
          <Legend
            wrapperStyle={{ color: '#ccc', paddingTop: 12 }}
          />

          {/* Cloud: Line for daily (too dense for bars), Bar otherwise */}
          {isDaily ? (
            <Line
              yAxisId="cloud"
              dataKey="cloud_coverage_avg"
              name="Cloud coverage"
              stroke={CLOUD_STROKE}
              strokeWidth={1.5}
              dot={false}
              connectNulls
            />
          ) : (
            <Bar
              yAxisId="cloud"
              dataKey="cloud_coverage_avg"
              name="Cloud coverage"
              fill={CLOUD_FILL}
              radius={[4, 4, 0, 0]}
            >
              {chartData.map((pt, idx) => (
                <Cell
                  key={idx}
                  fill={pt.interpolated ? CLOUD_FILL_FADED : CLOUD_FILL}
                  stroke={pt.interpolated ? CLOUD_STROKE_FADED : undefined}
                  strokeWidth={pt.interpolated ? 1 : 0}
                  strokeDasharray={pt.interpolated ? '3 2' : undefined}
                />
              ))}
            </Bar>
          )}

          {hasLightning && (
            <Line
              yAxisId="lightning"
              dataKey="lightning_probability"
              name="Lightning probability"
              stroke={LIGHTNING_STROKE}
              strokeWidth={isDaily ? 1.5 : 2}
              dot={isDaily ? false : { r: 4, fill: LIGHTNING_STROKE }}
              connectNulls
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {stations.length > 0 && (
        <div className="station-weights">
          <p className="weights-label">Based on data from:</p>
          <ul className="weights-list">
            {stations.map((s) => (
              <li key={s.id} className="weight-item">
                <span className="weight-name">{s.name}</span>
                <span className="weight-meta">
                  {s.distance_km} km &middot; {s.weight_pct}% weight
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
