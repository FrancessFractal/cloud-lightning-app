import { useState, useRef, useCallback, useEffect } from 'react'
import AddressSearch from './components/AddressSearch'
import InsightCards from './components/InsightCards'
import CloudChartPanel from './components/CloudChartPanel'
import LightningChartPanel from './components/LightningChartPanel'
import DataConfidenceBadge from './components/DataConfidenceBadge'
import DataSourcesDrawer from './components/DataSourcesDrawer'
import StationExplorer from './components/StationExplorer'
import './App.css'

const RESOLUTIONS = [
  { key: 'day', label: 'Daily' },
  { key: 'month', label: 'Monthly' },
  { key: 'year', label: 'Yearly' },
]

// ---------------------------------------------------------------------------
// URL ↔ state helpers
// ---------------------------------------------------------------------------

function getStateFromURL() {
  const path = window.location.pathname
  const params = new URLSearchParams(window.location.search)

  if (path === '/stations') {
    return { page: 'explorer', location: null }
  }

  const lat = parseFloat(params.get('lat'))
  const lng = parseFloat(params.get('lng'))
  const name = params.get('name')

  if (!isNaN(lat) && !isNaN(lng) && name) {
    return { page: 'search', location: { lat, lng, display_name: name } }
  }

  return { page: 'search', location: null }
}

function buildLocationURL(loc) {
  const params = new URLSearchParams({
    lat: String(loc.lat),
    lng: String(loc.lng),
    name: loc.display_name,
  })
  return `/?${params.toString()}`
}

// ---------------------------------------------------------------------------
// App
// ---------------------------------------------------------------------------

function App() {
  const initial = getStateFromURL()
  const [page, setPage] = useState(initial.page)
  const [location, setLocation] = useState(initial.location)
  const [weatherData, setWeatherData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [resolution, setResolution] = useState('month')
  const [activeLabel, setActiveLabel] = useState(null)
  const locationRef = useRef(initial.location)

  const fetchWeather = useCallback(async (loc, res) => {
    setWeatherData(null)
    setError(null)
    setLoading(true)

    try {
      const resp = await fetch(
        `/api/location-weather?lat=${loc.lat}&lng=${loc.lng}&resolution=${res}`
      )
      const data = await resp.json()

      if (!resp.ok || data.error) {
        setError(data.error || 'Failed to load weather data.')
      } else {
        setWeatherData(data)
      }
    } catch {
      setError('Failed to connect to backend.')
    } finally {
      setLoading(false)
    }
  }, [])

  // Deep-link: auto-fetch weather if URL already contains a location on mount
  const didMount = useRef(false)
  useEffect(() => {
    if (!didMount.current) {
      didMount.current = true
      if (initial.location) {
        fetchWeather(initial.location, 'month')
      }
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // --- Navigation helpers ---------------------------------------------------

  const navigateTo = useCallback((url, newPage, newLocation) => {
    history.pushState(null, '', url)
    setPage(newPage)
    setLocation(newLocation)
    locationRef.current = newLocation
    // Reset weather state when navigating away from a location
    if (!newLocation) {
      setWeatherData(null)
      setError(null)
    }
  }, [])

  const handleLocationFound = (loc) => {
    navigateTo(buildLocationURL(loc), 'search', loc)
    setResolution('month')
    fetchWeather(loc, 'month')
  }

  const handleTabClick = useCallback((e, targetPage) => {
    e.preventDefault()
    if (targetPage === page) return
    if (targetPage === 'explorer') {
      navigateTo('/stations', 'explorer', null)
    } else {
      // Going back to search — restore the current location URL if one exists
      const loc = locationRef.current
      const url = loc ? buildLocationURL(loc) : '/'
      navigateTo(url, 'search', loc)
      if (loc && !weatherData) {
        fetchWeather(loc, resolution)
      }
    }
  }, [page, navigateTo, weatherData, resolution, fetchWeather])

  // --- Popstate: browser back/forward ---------------------------------------

  useEffect(() => {
    const onPopState = () => {
      const { page: newPage, location: newLoc } = getStateFromURL()
      setPage(newPage)
      setLocation(newLoc)
      locationRef.current = newLoc

      if (newLoc) {
        setResolution('month')
        fetchWeather(newLoc, 'month')
      } else {
        setWeatherData(null)
        setError(null)
      }
    }
    window.addEventListener('popstate', onPopState)
    return () => window.removeEventListener('popstate', onPopState)
  }, [fetchWeather])

  const handleResolutionChange = (res) => {
    setResolution(res)
    if (locationRef.current) {
      // Only re-fetch the detail resolution; yearly is already cached
      setWeatherData(null)
      setError(null)
      setLoading(true)
      fetch(`/api/location-weather?lat=${locationRef.current.lat}&lng=${locationRef.current.lng}&resolution=${res}`)
        .then((r) => r.json())
        .then((data) => {
          if (data.error) setError(data.error)
          else setWeatherData(data)
        })
        .catch(() => setError('Failed to connect to backend.'))
        .finally(() => setLoading(false))
    }
  }

  const handleHover = useCallback((label) => setActiveLabel(label), [])

  // Crossfade: briefly fade out detail charts when resolution changes
  const [detailVisible, setDetailVisible] = useState(true)
  const prevResolution = useRef(resolution)
  useEffect(() => {
    if (prevResolution.current !== resolution) {
      prevResolution.current = resolution
      setDetailVisible(false)
      const id = requestAnimationFrame(() => setDetailVisible(true))
      return () => cancelAnimationFrame(id)
    }
  }, [resolution])

  return (
    <div className="app">
      <h1>Cloud &amp; Lightning Explorer</h1>
      <p className="subtitle">
        Historical climate patterns from SMHI open data
      </p>

      <nav className="tab-bar">
        <a
          className={`tab-btn ${page === 'search' ? 'active' : ''}`}
          href="/"
          onClick={(e) => handleTabClick(e, 'search')}
        >
          Search
        </a>
        <a
          className={`tab-btn ${page === 'explorer' ? 'active' : ''}`}
          href="/stations"
          onClick={(e) => handleTabClick(e, 'explorer')}
        >
          All stations
        </a>
      </nav>

      {page === 'search' && (
        <>
          {/* Location header */}
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

          {/* Insight cards */}
          {weatherData && <InsightCards data={weatherData} resolution={resolution} />}

          {/* Granularity toggle */}
          {weatherData && (
            <div className="granularity-toggle">
              {RESOLUTIONS.map((r) => (
                <button
                  key={r.key}
                  className={`res-btn ${resolution === r.key ? 'active' : ''}`}
                  onClick={() => handleResolutionChange(r.key)}
                >
                  {r.label}
                </button>
              ))}
            </div>
          )}

          {/* Detailed charts -- crossfade wrapper */}
          {weatherData && (
            <div className={`detail-fade ${detailVisible ? 'visible' : ''}`}>
              <CloudChartPanel
                data={weatherData}
                resolution={resolution}
                activeLabel={activeLabel}
                onHover={handleHover}
              />

              <LightningChartPanel
                data={weatherData}
                resolution={resolution}
                activeLabel={activeLabel}
                onHover={handleHover}
              />

              {!weatherData.has_lightning_data && (
                <p className="notice">
                  None of the nearby stations record present weather observations, so
                  lightning data is not available for this location.
                </p>
              )}
            </div>
          )}

          {/* Data quality badge */}
          {weatherData && (
            <DataConfidenceBadge quality={weatherData.quality} />
          )}

          {/* Low-quality warning */}
          {weatherData?.quality?.level === 'low' && (
            <div className="estimation-warning" role="alert">
              <span className="estimation-warning-icon" aria-hidden="true">&#9888;</span>
              <span>
                Data quality for this location is low — observations are sparse
                or stations are far away. Results may be less reliable. Try a
                location closer to a weather station for higher confidence.
              </span>
            </div>
          )}

          {/* Data sources drawer */}
          {weatherData && (
            <DataSourcesDrawer
              stations={weatherData.stations}
              center={location ? [location.lat, location.lng] : null}
            />
          )}
        </>
      )}

      {page === 'explorer' && <StationExplorer />}
    </div>
  )
}

export default App
