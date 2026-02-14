import { useState } from 'react'
import AddressSearch from './components/AddressSearch'
import StationSelector from './components/StationSelector'
import WeatherChart from './components/WeatherChart'
import StationExplorer from './components/StationExplorer'
import './App.css'

function App() {
  const [page, setPage] = useState('search')
  const [location, setLocation] = useState(null)
  const [stations, setStations] = useState([])
  const [selectedStation, setSelectedStation] = useState(null)
  const [weatherData, setWeatherData] = useState(null)
  const [loadingStations, setLoadingStations] = useState(false)
  const [loadingData, setLoadingData] = useState(false)

  const handleLocationFound = async (loc) => {
    setLocation(loc)
    setStations([])
    setSelectedStation(null)
    setWeatherData(null)
    setLoadingStations(true)

    try {
      const res = await fetch(`/api/stations?lat=${loc.lat}&lng=${loc.lng}`)
      const data = await res.json()
      setStations(data.stations || [])
    } catch {
      setStations([])
    } finally {
      setLoadingStations(false)
    }
  }

  const handleStationSelect = async (stationId) => {
    setSelectedStation(stationId)
    setWeatherData(null)
    setLoadingData(true)

    try {
      const res = await fetch(`/api/weather-data/${stationId}`)
      const data = await res.json()
      setWeatherData(data)
    } catch {
      setWeatherData(null)
    } finally {
      setLoadingData(false)
    }
  }

  const selectedStationName = stations.find((s) => s.id === selectedStation)?.name

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
            isLoading={loadingStations}
          />

          {location && (
            <div className="location-badge">
              <span className="location-icon">&#x1F4CD;</span> {location.display_name}
            </div>
          )}

          {loadingStations && <p className="loading">Loading nearby stations...</p>}

          <StationSelector
            stations={stations}
            selectedId={selectedStation}
            onSelect={handleStationSelect}
            isLoading={loadingData}
          />

          {loadingData && (
            <div className="loading">
              <p>Fetching climate data&hellip; This may take a moment.</p>
              <div className="spinner" />
            </div>
          )}

          <WeatherChart data={weatherData} stationName={selectedStationName} />
        </>
      )}

      {page === 'explorer' && <StationExplorer />}
    </div>
  )
}

export default App
