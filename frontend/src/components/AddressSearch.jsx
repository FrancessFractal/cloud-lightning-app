import { useState, useRef, useEffect, useCallback } from 'react'

export default function AddressSearch({ onLocationFound, isLoading, location }) {
  const [query, setQuery] = useState('')
  const [suggestions, setSuggestions] = useState([])
  const [highlighted, setHighlighted] = useState(-1)
  const [open, setOpen] = useState(false)
  const [error, setError] = useState(null)
  const [searching, setSearching] = useState(false)
  const [noResults, setNoResults] = useState(false)

  // Collapsed = location is set and user hasn't clicked to edit
  const [editing, setEditing] = useState(false)

  const wrapperRef = useRef(null)
  const inputRef = useRef(null)
  const abortRef = useRef(null)
  const debounceRef = useRef(null)

  // When a new location comes in from outside, collapse back
  useEffect(() => {
    if (location) {
      setEditing(false)
    }
  }, [location])

  // Close dropdown on outside click
  useEffect(() => {
    const handleClick = (e) => {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) {
        setOpen(false)
        // If user clicks outside while editing but a location exists, collapse
        if (location) setEditing(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [location])

  const expandToEdit = () => {
    setEditing(true)
    setQuery('')
    setError(null)
    setSuggestions([])
    setNoResults(false)
    // Focus input after render
    setTimeout(() => inputRef.current?.focus(), 50)
  }

  const fetchSuggestions = useCallback(async (q) => {
    if (q.length < 3) {
      setSuggestions([])
      setOpen(false)
      return
    }

    // Abort previous request
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const res = await fetch(
        `/api/autocomplete?q=${encodeURIComponent(q)}`,
        { signal: controller.signal }
      )
      const data = await res.json()
      const results = data.suggestions || []
      if (results.length > 0) {
        setSuggestions(results)
        setHighlighted(-1)
        setNoResults(false)
        setOpen(true)
      } else {
        setSuggestions([])
        setNoResults(true)
        setOpen(true)
      }
    } catch (err) {
      if (err.name !== 'AbortError') {
        setSuggestions([])
        setOpen(false)
      }
    }
  }, [])

  const handleChange = (e) => {
    const value = e.target.value
    setQuery(value)
    setError(null)
    setNoResults(false)

    // Debounce autocomplete
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => fetchSuggestions(value), 300)
  }

  const selectSuggestion = (suggestion) => {
    setQuery(suggestion.display_name)
    setSuggestions([])
    setOpen(false)
    setHighlighted(-1)
    onLocationFound(suggestion)
  }

  const handleSubmit = async (e) => {
    e.preventDefault()

    // If a suggestion is highlighted, select it
    if (highlighted >= 0 && highlighted < suggestions.length) {
      selectSuggestion(suggestions[highlighted])
      return
    }

    // Fallback: search with the full query
    if (!query.trim()) return
    setError(null)
    setSearching(true)
    setOpen(false)

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

  const handleKeyDown = (e) => {
    if (e.key === 'Escape') {
      setOpen(false)
      setHighlighted(-1)
      // Collapse back if there's already a location
      if (location) setEditing(false)
      return
    }
    if (!open || suggestions.length === 0) return

    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setHighlighted((prev) => (prev < suggestions.length - 1 ? prev + 1 : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setHighlighted((prev) => (prev > 0 ? prev - 1 : suggestions.length - 1))
    }
  }

  // --- Collapsed state: show location badge ---
  if (location && !editing && !isLoading) {
    return (
      <button
        className="location-badge location-badge-btn"
        onClick={expandToEdit}
        title="Click to change location"
      >
        <span className="location-badge-left">
          <span className="location-icon">&#x1F4CD;</span>
          <span className="location-name">{location.display_name}</span>
        </span>
        <span className="location-edit-hint">Change</span>
      </button>
    )
  }

  // --- Expanded state: show search form ---
  return (
    <div className="search-card" ref={wrapperRef}>
      <form onSubmit={handleSubmit} className="search-form">
        <div className="search-input-wrap">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={() => suggestions.length > 0 && setOpen(true)}
            placeholder="Enter a Swedish address or city..."
            disabled={searching || isLoading}
            autoComplete="off"
            autoFocus={!location}
          />
          {open && (suggestions.length > 0 || noResults) && (
            <ul className="suggestions">
              {suggestions.length > 0
                ? suggestions.map((s, i) => (
                    <li
                      key={`${s.lat}-${s.lng}`}
                      className={`suggestion-item ${i === highlighted ? 'highlighted' : ''}`}
                      onMouseDown={() => selectSuggestion(s)}
                      onMouseEnter={() => setHighlighted(i)}
                    >
                      {s.display_name}
                    </li>
                  ))
                : (
                    <li className="suggestion-empty">
                      No results for &ldquo;{query}&rdquo;
                    </li>
                  )
              }
            </ul>
          )}
        </div>
        <button type="submit" disabled={searching || isLoading || !query.trim()}>
          {searching ? 'Searching...' : 'Search'}
        </button>
      </form>
      {location && !isLoading && (
        <button
          className="search-cancel"
          type="button"
          onClick={() => setEditing(false)}
        >
          Cancel
        </button>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  )
}
