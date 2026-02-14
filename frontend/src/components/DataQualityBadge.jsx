import { useState, useRef, useEffect } from 'react'
import StationMap from './StationMap'

const LEVELS = {
  good: { label: 'High',   cls: 'dqb-high',   symbol: '\u2714' },
  fair: { label: 'Medium', cls: 'dqb-medium', symbol: '\u25CB' },
  poor: { label: 'Low',    cls: 'dqb-low',    symbol: '\u26A0' },
}

const DOT_CLS = { good: 'dot-good', fair: 'dot-fair', poor: 'dot-poor' }
const BAR_CLS = { good: 'bar-high', fair: 'bar-medium', poor: 'bar-low' }

function factorRow(label, value, level) {
  const pct = Math.round(Math.max(0, Math.min(100, value)))
  return (
    <div className="quality-row" key={label}>
      <span className={`quality-dot ${DOT_CLS[level] || 'dot-poor'}`} />
      <span className="quality-label">{label}</span>
      <div className="quality-track">
        <div
          className={`quality-fill ${BAR_CLS[level] || 'bar-low'}`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  )
}

export default function DataQualityBadge({ title, dim, stations, center }) {
  const [open, setOpen] = useState(false)
  const bodyRef = useRef(null)
  const [bodyHeight, setBodyHeight] = useState(0)

  useEffect(() => {
    if (open && bodyRef.current) {
      setBodyHeight(bodyRef.current.scrollHeight)
    }
  }, [open, stations])

  if (!dim) return null

  const { station_coverage, historical_data } = dim

  // Determine overall level for this dimension (worst of the two factors)
  const ORDER = { poor: 0, fair: 1, good: 2 }
  const worst = Math.min(ORDER[station_coverage.level] || 0, ORDER[historical_data.level] || 0)
  const level = ['poor', 'fair', 'good'][worst]
  const info = LEVELS[level] || LEVELS.poor

  return (
    <div className={`dqb ${info.cls}`}>
      <button
        className="dqb-header"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="dqb-title">
          <span className="dqb-symbol" aria-hidden="true">{info.symbol}</span>
          {' '}{title} Data Quality: {info.label}
        </span>
        <span className={`drawer-chevron ${open ? 'open' : ''}`}>&#9662;</span>
      </button>

      <div
        className="dqb-body-slide"
        style={{ maxHeight: open ? `${bodyHeight}px` : '0px' }}
        aria-hidden={!open}
      >
        <div className="dqb-body" ref={bodyRef}>
          {/* Quality bars */}
          <div className="dqb-factors">
            {factorRow('Station coverage', station_coverage.value, station_coverage.level)}
            {station_coverage.summary && (
              <p className="quality-factor-summary">{station_coverage.summary}</p>
            )}
            {factorRow('Historical data', historical_data.value, historical_data.level)}
            {historical_data.summary && (
              <p className="quality-factor-summary">{historical_data.summary}</p>
            )}
          </div>

          {/* Station map */}
          {center && stations && stations.length > 0 && (
            <StationMap center={center} stations={stations} />
          )}

          {/* Station table */}
          {stations && stations.length > 0 && (
            <table className="drawer-table">
              <thead>
                <tr>
                  <th>Station</th>
                  <th>Distance</th>
                  <th>Weight</th>
                </tr>
              </thead>
              <tbody>
                {stations.map((s) => (
                  <tr key={s.id}>
                    <td className="drawer-station-name">{s.name}</td>
                    <td className="drawer-mono">{s.distance_km} km</td>
                    <td className="drawer-mono">{s.weight_pct}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  )
}
