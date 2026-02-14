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

export default function WeatherChart({ data, stationName }) {
  if (!data || data.months.length === 0) return null

  return (
    <div className="card chart-card">
      <h2>Climate profile{stationName ? ` — ${stationName}` : ''}</h2>
      <p className="hint">
        Monthly averages based on historical observations
      </p>
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
          <Line
            yAxisId="lightning"
            dataKey="lightning_probability"
            name="Lightning probability"
            stroke="#f5a623"
            strokeWidth={2}
            dot={{ r: 4, fill: '#f5a623' }}
            connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
