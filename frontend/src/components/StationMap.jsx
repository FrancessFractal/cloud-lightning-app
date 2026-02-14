import { useMemo } from 'react'
import { MapContainer, TileLayer, CircleMarker, Marker, Tooltip, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Fix default marker icon path issue with bundlers
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

/**
 * Auto-fit the map bounds to include all markers.
 */
function FitBounds({ center, stations }) {
  const map = useMap()

  useMemo(() => {
    const points = [center, ...stations.map((s) => [s.latitude, s.longitude])]
    if (points.length > 0) {
      const bounds = L.latLngBounds(points)
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 11 })
    }
  }, [center, stations, map])

  return null
}

export default function StationMap({ center, stations }) {
  if (!center || !stations || stations.length === 0) return null

  // Scale circle radius by weight (min 6, max 18)
  const maxWeight = Math.max(...stations.map((s) => s.weight_pct))
  const radius = (pct) => 6 + (pct / maxWeight) * 12

  return (
    <div className="card station-map-card">
      <h3 className="map-title">Contributing stations</h3>
      <div className="map-container">
        <MapContainer
          center={center}
          zoom={8}
          scrollWheelZoom={false}
          style={{ height: '100%', width: '100%', borderRadius: 8 }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <FitBounds center={center} stations={stations} />

          {/* Searched location */}
          <Marker position={center}>
            <Tooltip permanent={false}>Your location</Tooltip>
          </Marker>

          {/* Station markers */}
          {stations.map((s) => (
            <CircleMarker
              key={s.id}
              center={[s.latitude, s.longitude]}
              radius={radius(s.weight_pct)}
              pathOptions={{
                color: 'rgba(100, 126, 234, 0.9)',
                fillColor: 'rgba(100, 126, 234, 0.5)',
                fillOpacity: 0.5,
                weight: 2,
              }}
            >
              <Tooltip>
                <strong>{s.name}</strong><br />
                {s.distance_km} km &middot; {s.weight_pct}% weight
              </Tooltip>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
    </div>
  )
}
