import { useState, useEffect } from 'react'
import './App.css'

function App() {
  const [message, setMessage] = useState('Loading...')

  useEffect(() => {
    fetch('/api/hello')
      .then((res) => res.json())
      .then((data) => setMessage(data.message))
      .catch(() => setMessage('Failed to connect to backend'))
  }, [])

  return (
    <div className="app">
      <h1>Weather App</h1>
      <div className="card">
        <p className="message">{message}</p>
      </div>
      <p className="hint">
        React frontend &harr; Python backend
      </p>
    </div>
  )
}

export default App
