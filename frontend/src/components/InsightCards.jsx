import { useMemo } from 'react'
import { generateInsights } from '../utils/chartHelpers'

export default function InsightCards({ data, resolution }) {
  const insights = useMemo(
    () => generateInsights(data.points, resolution, data.has_lightning_data),
    [data.points, resolution, data.has_lightning_data],
  )

  if (insights.length === 0) return null

  return (
    <div className="insight-cards">
      {insights.map((ins, i) => (
        <div key={i} className="insight-card">
          <span className="insight-value">{ins.value}</span>
          <span className="insight-label">{ins.label}</span>
        </div>
      ))}
    </div>
  )
}
