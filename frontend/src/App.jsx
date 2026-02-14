import { useState, useRef, useCallback, useEffect } from 'react'
import AddressSearch from './components/AddressSearch'
import AnnualSummaryCharts from './components/AnnualSummaryCharts'
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

function App() {
  const [page, setPage] = useState('search')
  const [location, setLocation] = useState(null)
  const [weatherData, setWeatherData] = useState(null)
  const [yearlyData, setYearlyData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [resolution, setResolution] = useState('month')
  const [activeLabel, setActiveLabel] = useState(null)
  const locationRef = useRef(null)

  const fetchWeather = useCallback(async (loc, res) => {
    setWeatherData(null)
    setError(null)
    setLoading(true)

    try {
      // Parallel fetch: selected resolution + yearly summary
      const baseUrl = `/api/location-weather?lat=${loc.lat}&lng=${loc.lng}`
      const [mainResp, yearResp] = await Promise.all([
        fetch(`${baseUrl}&resolution=${res}`),
        fetch(`${baseUrl}&resolution=year`),
      ])
      const mainData = await mainResp.json()
      const yearData = await yearResp.json()

      if (!mainResp.ok || mainData.error) {
        setError(mainData.error || 'Failed to load weather data.')
      } else {
        setWeatherData(mainData)
      }

      if (yearResp.ok && !yearData.error) {
        setYearlyData(yearData)
      }
    } catch {
      setError('Failed to connect to backend.')
    } finally {
      setLoading(false)
    }
  }, [])

  const handleLocationFound = (loc) => {
    setLocation(loc)
    locationRef.current = loc
    setYearlyData(null)
    fetchWeather(loc, resolution)
  }

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

          {/* Annual summary (always yearly) */}
          {yearlyData && <AnnualSummaryCharts data={yearlyData} />}

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

          {/* Data confidence badge */}
          {weatherData && (
            <DataConfidenceBadge measuredPct={weatherData.measured_pct} />
          )}

          {/* High-estimation warning */}
          {weatherData && weatherData.measured_pct != null && weatherData.measured_pct < 60 && (
            <div className="estimation-warning" role="alert">
              <span className="estimation-warning-icon" aria-hidden="true">&#9888;</span>
              <span>
                More than 40% of the data shown is estimated (interpolated from
                neighboring time periods). Results for this location may be less
                reliable. Try a different location closer to a weather station
                for higher confidence.
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
