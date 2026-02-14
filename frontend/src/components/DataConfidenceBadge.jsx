const LEVELS = {
  high:   { label: 'High',   cls: 'badge-high',   symbol: '\u2714' },
  medium: { label: 'Medium', cls: 'badge-medium', symbol: '\u25CB' },
  low:    { label: 'Low',    cls: 'badge-low',    symbol: '\u26A0' },
}

const DOT_CLS = { good: 'dot-good', fair: 'dot-fair', poor: 'dot-poor' }

const BAR_CLS = { good: 'bar-high', fair: 'bar-medium', poor: 'bar-low' }

function factorRow(label, value, level, detail) {
  const pct = Math.round(Math.max(0, Math.min(100, value)))
  const barCls = BAR_CLS[level] || 'bar-low'
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

  const { level, historical_data, station_coverage } = quality
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
          'Station coverage',
          station_coverage.value,
          station_coverage.level,
          '',
        )}
        {station_coverage.summary && (
          <p className="quality-factor-summary">{station_coverage.summary}</p>
        )}
        {factorRow(
          'Historical data',
          historical_data.value,
          historical_data.level,
          '',
        )}
        {historical_data.summary && (
          <p className="quality-factor-summary">{historical_data.summary}</p>
        )}
      </div>

      {level === 'low' && (
        <p className="quality-warning" role="alert">
          Results may be less reliable for this location due to limited
          nearby station data.
        </p>
      )}
    </div>
  )
}
