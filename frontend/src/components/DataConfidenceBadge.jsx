// Symbols provide a non-color signal for colorblind users
const LEVELS = {
  high:   { label: 'High',   cls: 'badge-high',   symbol: '\u2714' }, // ✔
  medium: { label: 'Medium', cls: 'badge-medium', symbol: '\u25CB' }, // ○
  low:    { label: 'Low',    cls: 'badge-low',    symbol: '\u26A0' }, // ⚠
}

export default function DataConfidenceBadge({ measuredPct }) {
  if (measuredPct == null) return null

  const estimated = Math.round((100 - measuredPct) * 10) / 10
  const measured = Math.round(measuredPct * 10) / 10

  const key = measured >= 85 ? 'high' : measured >= 60 ? 'medium' : 'low'
  const { label, cls, symbol } = LEVELS[key]

  return (
    <div className={`confidence-badge ${cls}`} role="status">
      <span className="confidence-level">
        <span className="confidence-symbol" aria-hidden="true">{symbol}</span>
        {' '}Data Confidence: {label}
      </span>
      <span className="confidence-detail">
        {measured}% Measured | {estimated}% Estimated
      </span>
    </div>
  )
}
