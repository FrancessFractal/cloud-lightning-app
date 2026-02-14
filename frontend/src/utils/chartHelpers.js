/**
 * Shared chart utility functions used by both CloudChartPanel and
 * LightningChartPanel.
 */

/**
 * Fill null gaps by linear interpolation. Returns a new array with
 * `interpolated: true` on filled-in points.
 */
export function interpolateGaps(points, fields = ['cloud_coverage_avg', 'lightning_probability']) {
  const result = points.map((p) => ({ ...p }))

  for (const field of fields) {
    let i = 0
    while (i < result.length) {
      if (result[i][field] != null) { i++; continue }

      const gapStart = i - 1
      let gapEnd = i
      while (gapEnd < result.length && result[gapEnd][field] == null) gapEnd++

      const leftVal = gapStart >= 0 ? result[gapStart][field] : null
      const rightVal = gapEnd < result.length ? result[gapEnd][field] : null

      if (leftVal != null && rightVal != null) {
        const span = gapEnd - gapStart
        for (let j = gapStart + 1; j < gapEnd; j++) {
          const t = (j - gapStart) / span
          result[j][field] = Math.round((leftVal + (rightVal - leftVal) * t) * 10) / 10
          result[j].interpolated = true
        }
      } else if (leftVal != null) {
        for (let j = gapStart + 1; j < gapEnd; j++) {
          result[j][field] = leftVal
          result[j].interpolated = true
        }
      } else if (rightVal != null) {
        for (let j = i; j < gapEnd; j++) {
          result[j][field] = rightVal
          result[j].interpolated = true
        }
      }

      i = gapEnd
    }
  }

  return result
}

/**
 * LOESS smoother. Adds `trend_cloud` to each point.
 */
export function addTrendLine(points, bandwidth = 0.25) {
  const obs = []
  for (let i = 0; i < points.length; i++) {
    const p = points[i]
    if (p.cloud_coverage_avg != null && !p.interpolated) {
      obs.push({ x: i, y: p.cloud_coverage_avg })
    }
  }
  if (obs.length < 4) return points

  const n = obs.length
  const windowSize = Math.max(Math.ceil(bandwidth * n), 3)
  const tricube = (d) => {
    if (d >= 1) return 0
    const t = 1 - d * d * d
    return t * t * t
  }

  return points.map((p, idx) => {
    const sorted = obs
      .map((o) => ({ ...o, dist: Math.abs(o.x - idx) }))
      .sort((a, b) => a.dist - b.dist)
      .slice(0, windowSize)

    const maxDist = sorted[sorted.length - 1].dist || 1
    let swSum = 0, swx = 0, swy = 0, swxy = 0, swx2 = 0
    for (const o of sorted) {
      const w = tricube(o.dist / maxDist)
      swSum += w; swx += w * o.x; swy += w * o.y
      swxy += w * o.x * o.y; swx2 += w * o.x * o.x
    }
    const denom = swSum * swx2 - swx * swx
    if (denom === 0) return p
    const b = (swSum * swxy - swx * swy) / denom
    const a = (swy - b * swx) / swSum
    return { ...p, trend_cloud: Math.round((a + b * idx) * 10) / 10 }
  })
}

/**
 * Compute insight objects from data points.
 * Returns array of { label, value, unit } objects.
 */
export function generateInsights(points, resolution, hasLightning) {
  const real = points.filter((p) => !p.interpolated && p.cloud_coverage_avg != null)
  if (real.length === 0) return []

  const insights = []
  const around = resolution === 'day' ? 'around ' : ''

  if (resolution === 'year') {
    const years = real.map((p) => parseInt(p.label, 10))
    const minY = Math.min(...years)
    const maxY = Math.max(...years)
    const first = real.filter((p) => parseInt(p.label, 10) < minY + 10)
    const last = real.filter((p) => parseInt(p.label, 10) > maxY - 10)
    if (first.length && last.length) {
      const earlyAvg = Math.round(first.reduce((s, p) => s + p.cloud_coverage_avg, 0) / first.length)
      const lateAvg = Math.round(last.reduce((s, p) => s + p.cloud_coverage_avg, 0) / last.length)
      const dir = lateAvg - earlyAvg
      const trend = dir > 2 ? 'Increasing' : dir < -2 ? 'Decreasing' : 'Stable'
      insights.push({ label: 'Cloud trend', value: `${trend} (${earlyAvg}% → ${lateAvg}%)` })
    }
  } else {
    let minPt = real[0], maxPt = real[0]
    for (const p of real) {
      if (p.cloud_coverage_avg < minPt.cloud_coverage_avg) minPt = p
      if (p.cloud_coverage_avg > maxPt.cloud_coverage_avg) maxPt = p
    }
    insights.push({ label: `Clearest ${around}${minPt.label}`, value: `${minPt.cloud_coverage_avg}%` })
    insights.push({ label: `Cloudiest ${around}${maxPt.label}`, value: `${maxPt.cloud_coverage_avg}%` })
  }

  if (hasLightning) {
    const realLt = points.filter(
      (p) => !p.interpolated && p.lightning_probability != null && p.lightning_probability > 0
    )
    if (realLt.length > 0) {
      let peak = realLt[0]
      for (const p of realLt) {
        if (p.lightning_probability > peak.lightning_probability) peak = p
      }
      insights.push({ label: `Lightning peak ${around}${peak.label}`, value: fmtLightning(peak.lightning_probability) })
    }

    const realLtAll = points.filter((p) => !p.interpolated && p.lightning_probability != null)
    if (realLtAll.length > 0) {
      let low = realLtAll[0]
      for (const p of realLtAll) {
        if (p.lightning_probability < low.lightning_probability) low = p
      }
      if (low.lightning_probability !== undefined && resolution !== 'year') {
        insights.push({ label: `Lowest lightning ${around}${low.label}`, value: fmtLightning(low.lightning_probability) })
      }
    }
  }

  return insights
}

/**
 * Format lightning probability for display. Values between 0 (exclusive)
 * and 1 (exclusive) are shown as "<1%" for readability.
 */
export function fmtLightning(val) {
  if (val == null) return 'N/A'
  if (val === 0) return '0%'
  if (val > 0 && val < 1) return '<1%'
  return `${val}%`
}

/**
 * Return an array of "round" year labels to show as XAxis ticks.
 * Picks multiples of 5 or 10 depending on the span, plus always
 * includes the first and last year so the range is clear.
 */
export function yearlyTicks(points) {
  if (!points || points.length === 0) return undefined
  const years = points.map((p) => parseInt(p.label, 10)).filter(Number.isFinite)
  if (years.length <= 15) return undefined // show all — Recharts default

  const min = Math.min(...years)
  const max = Math.max(...years)
  const span = max - min

  // Choose a step that's a "nice" number
  let step
  if (span <= 30) step = 2
  else if (span <= 60) step = 5
  else step = 10

  const ticks = []
  // First round year >= min
  const first = Math.ceil(min / step) * step
  for (let y = first; y <= max; y += step) {
    ticks.push(String(y))
  }
  // Always include the actual first and last year
  const minStr = String(min)
  const maxStr = String(max)
  if (!ticks.includes(minStr)) ticks.unshift(minStr)
  if (!ticks.includes(maxStr)) ticks.push(maxStr)

  return ticks
}

/**
 * Format XAxis ticks for daily resolution -- show month names only.
 */
export function dailyTickFormatter(label) {
  if (label.endsWith(' 01')) return label.replace(/ 01$/, '')
  return ''
}
