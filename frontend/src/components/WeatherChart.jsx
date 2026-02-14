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

const TREND_STROKE = 'rgba(100, 126, 234, 0.45)'

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

/**
 * Generate a plain-language summary from the data points.
 */
function generateSummary(points, resolution, hasLightning) {
  // Filter to real (non-interpolated) points with cloud data
  const realCloud = points.filter((p) => !p.interpolated && p.cloud_coverage_avg != null)
  if (realCloud.length === 0) return null

  const parts = []

  if (resolution === 'year') {
    // Decade averages for first and last decade
    const years = realCloud.map((p) => parseInt(p.label, 10))
    const minYear = Math.min(...years)
    const maxYear = Math.max(...years)
    const firstDecade = realCloud.filter((p) => parseInt(p.label, 10) < minYear + 10)
    const lastDecade = realCloud.filter((p) => parseInt(p.label, 10) > maxYear - 10)

    if (firstDecade.length > 0 && lastDecade.length > 0) {
      const earlyAvg = Math.round(firstDecade.reduce((s, p) => s + p.cloud_coverage_avg, 0) / firstDecade.length)
      const lateAvg = Math.round(lastDecade.reduce((s, p) => s + p.cloud_coverage_avg, 0) / lastDecade.length)
      const diff = lateAvg - earlyAvg
      const direction = diff > 2 ? 'increased' : diff < -2 ? 'decreased' : 'remained roughly stable'
      parts.push(
        `Cloud coverage has ${direction} from ~${earlyAvg}% in the ${Math.floor(minYear / 10) * 10}s to ~${lateAvg}% in the ${Math.floor(maxYear / 10) * 10}s.`
      )
    }
  } else {
    // Day or month: find clearest and cloudiest
    let minPt = realCloud[0]
    let maxPt = realCloud[0]
    for (const p of realCloud) {
      if (p.cloud_coverage_avg < minPt.cloud_coverage_avg) minPt = p
      if (p.cloud_coverage_avg > maxPt.cloud_coverage_avg) maxPt = p
    }

    const around = resolution === 'day' ? 'around ' : ''
    parts.push(`Clearest ${around}${minPt.label} (${minPt.cloud_coverage_avg}%).`)
    parts.push(`Cloudiest ${around}${maxPt.label} (${maxPt.cloud_coverage_avg}%).`)

    // Lightning peak
    if (hasLightning) {
      const realLightning = points.filter(
        (p) => !p.interpolated && p.lightning_probability != null && p.lightning_probability > 0
      )
      if (realLightning.length > 0) {
        let peakLt = realLightning[0]
        for (const p of realLightning) {
          if (p.lightning_probability > peakLt.lightning_probability) peakLt = p
        }
        parts.push(`Lightning peaks ${around}${peakLt.label} at ${peakLt.lightning_probability}%.`)
      }
    }
  }

  return parts.join(' ')
}

/**
 * LOESS (locally weighted scatterplot smoothing) over cloud data.
 * Produces a smooth curve that follows the data's local trends.
 *
 * @param {Array} points - chart data points
 * @param {number} bandwidth - fraction of data used per local fit (0–1).
 *   Smaller = more responsive, larger = smoother. 0.25 is a good default.
 */
function addTrendLine(points, bandwidth = 0.25) {
  // Collect valid (non-interpolated, non-null) observations with their index
  const obs = []
  for (let i = 0; i < points.length; i++) {
    const p = points[i]
    if (p.cloud_coverage_avg != null && !p.interpolated) {
      obs.push({ x: i, y: p.cloud_coverage_avg })
    }
  }

  if (obs.length < 4) return points

  const n = obs.length
  const windowSize = Math.max(Math.ceil(bandwidth * n), 3)

  // Tricube weight kernel
  const tricube = (d) => {
    if (d >= 1) return 0
    const t = 1 - d * d * d
    return t * t * t
  }

  // For each point index, compute a locally weighted linear fit
  return points.map((p, idx) => {
    // Sort observations by distance from idx and take the nearest windowSize
    const sorted = obs
      .map((o) => ({ ...o, dist: Math.abs(o.x - idx) }))
      .sort((a, b) => a.dist - b.dist)
      .slice(0, windowSize)

    const maxDist = sorted[sorted.length - 1].dist || 1

    // Weighted least squares (linear: y = a + b*x)
    let swSum = 0, swx = 0, swy = 0, swxy = 0, swx2 = 0
    for (const o of sorted) {
      const w = tricube(o.dist / maxDist)
      swSum += w
      swx += w * o.x
      swy += w * o.y
      swxy += w * o.x * o.y
      swx2 += w * o.x * o.x
    }

    const denom = swSum * swx2 - swx * swx
    if (denom === 0) return p

    const b = (swSum * swxy - swx * swy) / denom
    const a = (swy - b * swx) / swSum
    const fitted = a + b * idx

    return { ...p, trend_cloud: Math.round(fitted * 10) / 10 }
  })
}

export default function WeatherChart({ data, locationName, resolution, onResolutionChange }) {
  if (!data || !data.points || data.points.length === 0) return null

  const hasLightning = data.has_lightning_data
  const stations = data.stations || []
  const isDaily = resolution === 'day'

  const interpolated = useMemo(() => interpolateGaps(data.points), [data.points])
  const chartData = useMemo(
    () => (resolution === 'year' ? addTrendLine(interpolated) : interpolated),
    [interpolated, resolution],
  )
  const hasInterpolated = useMemo(
    () => chartData.some((p) => p.interpolated),
    [chartData],
  )
  const summary = useMemo(
    () => generateSummary(data.points, resolution, hasLightning),
    [data.points, resolution, hasLightning],
  )
  const showTrend = resolution === 'year' && chartData.some((p) => p.trend_cloud != null)

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

      {summary && (
        <p className="climate-summary">{summary}</p>
      )}

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

          {showTrend && (
            <Line
              yAxisId="cloud"
              dataKey="trend_cloud"
              name="Cloud trend"
              stroke={TREND_STROKE}
              strokeWidth={2}
              strokeDasharray="6 3"
              dot={false}
              legendType="plainline"
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
