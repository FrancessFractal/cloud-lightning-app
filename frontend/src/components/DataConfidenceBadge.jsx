const LEVELS = {
  high:   { label: 'High',   cls: 'badge-high',   symbol: '\u2714' }, // ✔
  medium: { label: 'Medium', cls: 'badge-medium', symbol: '\u25CB' }, // ○
  low:    { label: 'Low',    cls: 'badge-low',    symbol: '\u26A0' }, // ⚠
}

function scoreBar(value, label) {
  const pct = Math.round(Math.max(0, Math.min(100, value)))
  const cls = pct >= 70 ? 'bar-high' : pct >= 40 ? 'bar-medium' : 'bar-low'
  return (
    <div className="quality-row">
      <span className="quality-label">{label}</span>
      <div className="quality-track">
        <div className={`quality-fill ${cls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="quality-pct">{pct}%</span>
    </div>
  )
}

export default function DataConfidenceBadge({ quality }) {
  if (!quality) return null

  const { score, level, coverage_pct, depth_score, proximity_score, avg_distance_km, median_obs } = quality
  const info = LEVELS[level] || LEVELS.low

  return (
    <div className={`confidence-badge ${info.cls}`} role="status">
      <div className="confidence-header">
        <span className="confidence-level">
          <span className="confidence-symbol" aria-hidden="true">{info.symbol}</span>
          {' '}Data Quality: {info.label}
        </span>
        <span className="confidence-score">{Math.round(score)}/100</span>
      </div>

      <div className="quality-bars">
        {scoreBar(depth_score, 'Observation depth')}
        {scoreBar(coverage_pct, 'Data coverage')}
        {scoreBar(proximity_score, 'Station proximity')}
      </div>

      <div className="quality-meta">
        {avg_distance_km != null && (
          <span className="quality-meta-item">
            Avg station distance: {avg_distance_km} km
          </span>
        )}
        {median_obs > 0 && (
          <span className="quality-meta-item">
            Median observations per point: {median_obs.toLocaleString()}
          </span>
        )}
      </div>
    </div>
  )
}
