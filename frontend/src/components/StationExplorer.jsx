import { useState, useEffect, useMemo } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const SWEDEN_CENTER = [63.0, 16.5]
const SWEDEN_BOUNDS = L.latLngBounds([55.3, 10.5], [69.1, 24.2])

const COLOR_BOTH = { color: '#7cc47f', fillColor: '#7cc47f', fillOpacity: 0.55, weight: 1.5 }
const COLOR_CLOUD = { color: '#f5a623', fillColor: '#f5a623', fillOpacity: 0.55, weight: 1.5 }
const COLOR_LIGHTNING = { color: '#8ba8f5', fillColor: '#8ba8f5', fillOpacity: 0.55, weight: 1.5 }

function stationType(s) {
  if (s.has_cloud_data && s.has_weather_data) return 'both'
  if (s.has_cloud_data) return 'cloud-only'
  return 'lightning-only'
}

function stationColor(s) {
  const t = stationType(s)
  if (t === 'both') return COLOR_BOTH
  if (t === 'cloud-only') return COLOR_CLOUD
  return COLOR_LIGHTNING
}

function stationLabel(s) {
  const t = stationType(s)
  if (t === 'both') return 'Cloud + Lightning'
  if (t === 'cloud-only') return 'Cloud only'
  return 'Lightning only'
}

function FitSweden() {
  const map = useMap()
  useMemo(() => {
    map.fitBounds(SWEDEN_BOUNDS, { padding: [10, 10] })
  }, [map])
  return null
}

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
    if (filter === 'both' && stationType(s) !== 'both') return false
    if (filter === 'cloud-only' && stationType(s) !== 'cloud-only') return false
    if (filter === 'lightning-only' && stationType(s) !== 'lightning-only') return false
    if (search && !s.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const countBoth = stations.filter((s) => stationType(s) === 'both').length
  const countCloudOnly = stations.filter((s) => stationType(s) === 'cloud-only').length
  const countLightningOnly = stations.filter((s) => stationType(s) === 'lightning-only').length

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
            <span className="stat-label">Cloud + Lightning</span>
          </div>
          <div className="stat">
            <span className="stat-value stat-warn">{countCloudOnly}</span>
            <span className="stat-label">Cloud only</span>
          </div>
          <div className="stat">
            <span className="stat-value stat-info">{countLightningOnly}</span>
            <span className="stat-label">Lightning only</span>
          </div>
        </div>
      </div>

      {/* Station map */}
      <div className="card explorer-map-card">
        <h2>Station locations</h2>
        <div className="explorer-map-legend">
          <span className="explorer-legend-item">
            <span className="explorer-dot" style={{ background: COLOR_BOTH.fillColor }} />
            Cloud + Lightning
          </span>
          <span className="explorer-legend-item">
            <span className="explorer-dot" style={{ background: COLOR_CLOUD.fillColor }} />
            Cloud only
          </span>
          <span className="explorer-legend-item">
            <span className="explorer-dot" style={{ background: COLOR_LIGHTNING.fillColor }} />
            Lightning only
          </span>
        </div>
        <div className="explorer-map-container">
          <MapContainer
            center={SWEDEN_CENTER}
            zoom={4}
            scrollWheelZoom
            style={{ height: '100%', width: '100%', borderRadius: 8 }}
          >
            <TileLayer
              attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
            />
            <FitSweden />

            {filtered.map((s) => (
              <CircleMarker
                key={s.id}
                center={[s.latitude, s.longitude]}
                radius={6}
                pathOptions={stationColor(s)}
              >
                <Tooltip>
                  <strong>{s.name}</strong><br />
                  ID: {s.id}<br />
                  {stationLabel(s)}
                </Tooltip>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>
        <p className="hint" style={{ marginTop: '0.5em' }}>
          Showing {filtered.length} of {stations.length} stations
        </p>
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
            <button
              className={`filter-btn ${filter === 'lightning-only' ? 'active' : ''}`}
              onClick={() => setFilter('lightning-only')}
            >
              Lightning only ({countLightningOnly})
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
                <th>Cloud</th>
                <th>Lightning</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((s) => (
                <tr key={s.id}>
                  <td className="station-name-cell">{s.name}</td>
                  <td className="mono">{s.id}</td>
                  <td className="mono">{s.latitude.toFixed(2)}</td>
                  <td className="mono">{s.longitude.toFixed(2)}</td>
                  <td>
                    {s.has_cloud_data
                      ? <span className="badge badge-yes">Yes</span>
                      : <span className="badge badge-no">No</span>
                    }
                  </td>
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
