import { useState, useRef, useEffect } from 'react'
import StationMap from './StationMap'

export default function DataSourcesDrawer({ stations, center }) {
  const [open, setOpen] = useState(false)
  const contentRef = useRef(null)
  const [contentHeight, setContentHeight] = useState(0)

  // Measure content height whenever it changes or drawer opens
  useEffect(() => {
    if (open && contentRef.current) {
      setContentHeight(contentRef.current.scrollHeight)
    }
  }, [open, stations])

  if (!stations || stations.length === 0) return null

  return (
    <div className="data-drawer">
      <button
        className="drawer-toggle"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="drawer-toggle-label">
          Data Sources ({stations.length} station{stations.length !== 1 ? 's' : ''})
        </span>
        <span className={`drawer-chevron ${open ? 'open' : ''}`}>&#9662;</span>
      </button>

      <div
        className="drawer-slide"
        style={{ maxHeight: open ? `${contentHeight}px` : '0px' }}
        aria-hidden={!open}
      >
        <div className="drawer-content" ref={contentRef}>
          <p className="drawer-explanation">
            Data is calculated using weighted averages from nearby weather stations.
            Closer stations contribute more to final values.
          </p>

          {center && (
            <StationMap center={center} stations={stations} />
          )}

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
        </div>
      </div>
    </div>
  )
}
