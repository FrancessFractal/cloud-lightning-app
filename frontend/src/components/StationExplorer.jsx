import { useState, useEffect } from 'react'

export default function StationExplorer() {
  const [stations, setStations] = useState([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('all')
  const [search, setSearch] = useState('')

  useEffect(() => {
    fetch('/api/all-stations')
      .then((res) => res.json())
      .then((data) => setStations(data.stations || []))
      .catch(() => setStations([]))
      .finally(() => setLoading(false))
  }, [])

  const filtered = stations.filter((s) => {
    if (filter === 'both' && !s.has_weather_data) return false
    if (filter === 'cloud-only' && s.has_weather_data) return false
    if (search && !s.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const countBoth = stations.filter((s) => s.has_weather_data).length
  const countCloudOnly = stations.filter((s) => !s.has_weather_data).length

  if (loading) {
    return (
      <div className="card">
        <p className="loading">Loading station data...</p>
        <div className="spinner" />
      </div>
    )
  }

  return (
    <div className="explorer">
      <div className="card">
        <h2>Station overview</h2>
        <div className="explorer-stats">
          <div className="stat">
            <span className="stat-value">{stations.length}</span>
            <span className="stat-label">Total stations</span>
          </div>
          <div className="stat">
            <span className="stat-value stat-good">{countBoth}</span>
            <span className="stat-label">Cloud + lightning</span>
          </div>
          <div className="stat">
            <span className="stat-value stat-warn">{countCloudOnly}</span>
            <span className="stat-label">Cloud only</span>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="explorer-controls">
          <input
            type="text"
            placeholder="Filter by name..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="explorer-search"
          />
          <div className="explorer-filters">
            <button
              className={`filter-btn ${filter === 'all' ? 'active' : ''}`}
              onClick={() => setFilter('all')}
            >
              All ({stations.length})
            </button>
            <button
              className={`filter-btn ${filter === 'both' ? 'active' : ''}`}
              onClick={() => setFilter('both')}
            >
              Cloud + Lightning ({countBoth})
            </button>
            <button
              className={`filter-btn ${filter === 'cloud-only' ? 'active' : ''}`}
              onClick={() => setFilter('cloud-only')}
            >
              Cloud only ({countCloudOnly})
            </button>
          </div>
        </div>

        <div className="explorer-table-wrap">
          <table className="explorer-table">
            <thead>
              <tr>
                <th>Station</th>
                <th>ID</th>
                <th>Lat</th>
                <th>Lng</th>
                <th>Cloud data</th>
                <th>Lightning data</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id}>
                  <td className="station-name-cell">{s.name}</td>
                  <td className="mono">{s.id}</td>
                  <td className="mono">{s.latitude.toFixed(2)}</td>
                  <td className="mono">{s.longitude.toFixed(2)}</td>
                  <td><span className="badge badge-yes">Yes</span></td>
                  <td>
                    {s.has_weather_data
                      ? <span className="badge badge-yes">Yes</span>
                      : <span className="badge badge-no">No</span>
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {filtered.length === 0 && (
          <p className="hint" style={{ textAlign: 'center', padding: '1em 0' }}>
            No stations match the current filter.
          </p>
        )}
      </div>
    </div>
  )
}
