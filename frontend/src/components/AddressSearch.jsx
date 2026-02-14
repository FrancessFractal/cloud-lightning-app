import { useState } from 'react'

export default function AddressSearch({ onLocationFound, isLoading }) {
  const [query, setQuery] = useState('')
  const [error, setError] = useState(null)
  const [searching, setSearching] = useState(false)

  const handleSearch = async (e) => {
    e.preventDefault()
    if (!query.trim()) return

    setError(null)
    setSearching(true)

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(query)}`)
      const data = await res.json()

      if (!res.ok) {
        setError(data.error || 'Search failed')
        return
      }

      onLocationFound(data)
    } catch {
      setError('Could not connect to the server')
    } finally {
      setSearching(false)
    }
  }

  return (
    <div className="card">
      <h2>Find a location</h2>
      <form onSubmit={handleSearch} className="search-form">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Enter a Swedish address or city..."
          disabled={searching || isLoading}
        />
        <button type="submit" disabled={searching || isLoading || !query.trim()}>
          {searching ? 'Searching...' : 'Search'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </div>
  )
}
