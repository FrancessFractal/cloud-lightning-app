export default function StationSelector({ stations, selectedId, onSelect, isLoading }) {
  if (!stations || stations.length === 0) return null

  return (
    <div className="card">
      <h2>Nearby weather stations</h2>
      <p className="hint">Select a station to view its climate data</p>
      <ul className="station-list">
        {stations.map((s) => (
          <li key={s.id}>
            <button
              className={`station-btn ${selectedId === s.id ? 'active' : ''}`}
              onClick={() => onSelect(s.id)}
              disabled={isLoading}
            >
              <span className="station-name">{s.name}</span>
              <span className="station-dist">{s.distance_km} km</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
