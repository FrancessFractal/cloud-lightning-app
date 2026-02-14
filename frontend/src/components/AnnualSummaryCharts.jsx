import CloudChartPanel from './CloudChartPanel'
import LightningChartPanel from './LightningChartPanel'

export default function AnnualSummaryCharts({ data }) {
  if (!data || !data.points || data.points.length === 0) return null

  return (
    <div className="annual-summary card">
      <h2 className="annual-summary-title">Long-term Overview</h2>
      <p className="hint">All-time yearly averages across contributing stations</p>
      <CloudChartPanel
        data={data}
        resolution="year"
        height={180}
        compact
      />
      <LightningChartPanel
        data={data}
        resolution="year"
        height={180}
        compact
      />
    </div>
  )
}
