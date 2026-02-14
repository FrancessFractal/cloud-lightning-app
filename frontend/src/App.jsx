import { useState } from 'react'
import AddressSearch from './components/AddressSearch'
import WeatherChart from './components/WeatherChart'
import StationExplorer from './components/StationExplorer'
import './App.css'

function App() {
  const [page, setPage] = useState('search')
  const [location, setLocation] = useState(null)
  const [weatherData, setWeatherData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handleLocationFound = async (loc) => {
    setLocation(loc)
    setWeatherData(null)
    setError(null)
    setLoading(true)

    try {
      const res = await fetch(`/api/location-weather?lat=${loc.lat}&lng=${loc.lng}`)
      const data = await res.json()
      if (!res.ok || data.error) {
        setError(data.error || 'Failed to load weather data.')
      } else {
        setWeatherData(data)
      }
    } catch {
      setError('Failed to connect to backend.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="app">
      <h1>Weather App</h1>
      <p className="subtitle">
        Cloud coverage &amp; lightning data from SMHI
      </p>

      <nav className="tab-bar">
        <button
          className={`tab-btn ${page === 'search' ? 'active' : ''}`}
          onClick={() => setPage('search')}
        >
          Search
        </button>
        <button
          className={`tab-btn ${page === 'explorer' ? 'active' : ''}`}
          onClick={() => setPage('explorer')}
        >
          All stations
        </button>
      </nav>

      {page === 'search' && (
        <>
          <AddressSearch
            onLocationFound={handleLocationFound}
            isLoading={loading}
          />

          {location && (
            <div className="location-badge">
              <span className="location-icon">&#x1F4CD;</span> {location.display_name}
            </div>
          )}

          {loading && (
            <div className="loading">
              <p>Estimating weather patterns&hellip; This may take a moment for first-time lookups.</p>
              <div className="spinner" />
            </div>
          )}

          {error && (
            <div className="card" style={{ borderColor: 'rgba(229, 115, 115, 0.4)' }}>
              <p className="error">{error}</p>
            </div>
          )}

          <WeatherChart data={weatherData} locationName={location?.display_name} />
        </>
      )}

      {page === 'explorer' && <StationExplorer />}
    </div>
  )
}

export default App
