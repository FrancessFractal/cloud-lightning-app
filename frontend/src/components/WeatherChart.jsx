import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

export default function WeatherChart({ data, locationName }) {
  if (!data || !data.months || data.months.length === 0) return null

  const hasLightning = data.has_lightning_data
  const stations = data.stations || []

  // Shorten location to city/region (first two comma-separated parts)
  const shortLocation = locationName
    ? locationName.split(',').slice(0, 2).join(',').trim()
    : null

  return (
    <div className="card chart-card">
      <h2>Climate estimate{shortLocation ? ` — ${shortLocation}` : ''}</h2>
      <p className="hint">
        Weighted blend of {stations.length} nearby SMHI station{stations.length !== 1 ? 's' : ''}
      </p>

      {!hasLightning && (
        <p className="notice">
          None of the nearby stations record present weather observations, so
          lightning data is not available.
        </p>
      )}

      <ResponsiveContainer width="100%" height={380}>
        <ComposedChart
          data={data.months}
          margin={{ top: 10, right: 20, left: 0, bottom: 0 }}
        >
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
          <XAxis
            dataKey="month"
            tick={{ fill: '#aaa', fontSize: 13 }}
          />
          <YAxis
            yAxisId="cloud"
            domain={[0, 100]}
            tick={{ fill: '#aaa', fontSize: 13 }}
            label={{
              value: 'Cloud coverage %',
              angle: -90,
              position: 'insideLeft',
              style: { fill: '#aaa', fontSize: 12 },
            }}
          />
          {hasLightning && (
            <YAxis
              yAxisId="lightning"
              orientation="right"
              domain={[0, 'auto']}
              tick={{ fill: '#aaa', fontSize: 13 }}
              label={{
                value: 'Lightning prob. %',
                angle: 90,
                position: 'insideRight',
                style: { fill: '#aaa', fontSize: 12 },
              }}
            />
          )}
          <Tooltip
            contentStyle={{
              background: '#1e1e2e',
              border: '1px solid rgba(255,255,255,0.15)',
              borderRadius: 8,
              color: '#ddd',
            }}
            formatter={(value, name) => {
              if (value == null) return ['N/A', name]
              return [`${value}%`, name]
            }}
          />
          <Legend
            wrapperStyle={{ color: '#ccc', paddingTop: 12 }}
          />
          <Bar
            yAxisId="cloud"
            dataKey="cloud_coverage_avg"
            name="Cloud coverage"
            fill="rgba(100, 126, 234, 0.7)"
            radius={[4, 4, 0, 0]}
          />
          {hasLightning && (
            <Line
              yAxisId="lightning"
              dataKey="lightning_probability"
              name="Lightning probability"
              stroke="#f5a623"
              strokeWidth={2}
              dot={{ r: 4, fill: '#f5a623' }}
              connectNulls
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {stations.length > 0 && (
        <div className="station-weights">
          <p className="weights-label">Based on data from:</p>
          <ul className="weights-list">
            {stations.map((s) => (
              <li key={s.id} className="weight-item">
                <span className="weight-name">{s.name}</span>
                <span className="weight-meta">
                  {s.distance_km} km &middot; {s.weight_pct}% weight
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
