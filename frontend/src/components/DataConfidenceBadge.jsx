const LEVELS = {
  high:   { label: 'High',   cls: 'badge-high',   symbol: '\u2714' },
  medium: { label: 'Medium', cls: 'badge-medium', symbol: '\u25CB' },
  low:    { label: 'Low',    cls: 'badge-low',    symbol: '\u26A0' },
}

const DOT_CLS = { good: 'dot-good', fair: 'dot-fair', poor: 'dot-poor' }

function factorRow(label, value, level, detail) {
  const pct = Math.round(Math.max(0, Math.min(100, value)))
  const barCls = pct >= 70 ? 'bar-high' : pct >= 40 ? 'bar-medium' : 'bar-low'
  return (
    <div className="quality-row" key={label}>
      <span className={`quality-dot ${DOT_CLS[level] || 'dot-poor'}`} />
      <span className="quality-label">{label}</span>
      <div className="quality-track">
        <div className={`quality-fill ${barCls}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="quality-detail">{detail}</span>
    </div>
  )
}

export default function DataConfidenceBadge({ quality }) {
  if (!quality) return null

  const { level, coverage, depth, proximity, direction, median_obs } = quality
  const info = LEVELS[level] || LEVELS.low

  return (
    <div className={`confidence-badge ${info.cls}`} role="status">
      <div className="confidence-header">
        <span className="confidence-level">
          <span className="confidence-symbol" aria-hidden="true">{info.symbol}</span>
          {' '}Data Quality: {info.label}
        </span>
      </div>

      <div className="quality-bars">
        {factorRow(
          'Data coverage',
          coverage.value,
          coverage.level,
          `${coverage.value}%`,
        )}
        {factorRow(
          'Observation depth',
          depth.value,
          depth.level,
          `${depth.value}%`,
        )}
        {factorRow(
          'Station proximity',
          proximity.value,
          proximity.level,
          proximity.avg_km != null ? `${proximity.avg_km} km avg` : '',
        )}
        {factorRow(
          'Directional coverage',
          direction.value,
          direction.level,
          `${direction.spread_deg}\u00B0 spread`,
        )}
      </div>

      {median_obs > 0 && (
        <div className="quality-meta">
          <span className="quality-meta-item">
            Median observations per point: {median_obs.toLocaleString()}
          </span>
        </div>
      )}
    </div>
  )
}
