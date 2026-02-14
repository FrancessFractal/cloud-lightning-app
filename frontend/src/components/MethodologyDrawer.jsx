import { useState, useRef, useEffect } from 'react'

export default function MethodologyDrawer() {
  const [open, setOpen] = useState(false)
  const bodyRef = useRef(null)
  const [bodyHeight, setBodyHeight] = useState(0)

  useEffect(() => {
    if (open && bodyRef.current) {
      setBodyHeight(bodyRef.current.scrollHeight)
    }
  }, [open])

  return (
    <div className="methodology">
      <button
        className="methodology-header"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="methodology-title">
          <span className="methodology-icon" aria-hidden="true">&#9432;</span>
          {' '}How is this calculated?
        </span>
        <span className={`drawer-chevron ${open ? 'open' : ''}`}>&#9662;</span>
      </button>

      <div
        className="methodology-slide"
        style={{ maxHeight: open ? `${bodyHeight}px` : '0px' }}
        aria-hidden={!open}
      >
        <div className="methodology-body" ref={bodyRef}>
          <section className="methodology-section">
            <h4>Data source</h4>
            <p>
              All data comes from <strong>SMHI</strong> (Swedish Meteorological and
              Hydrological Institute) open data. Two types of observations are used:
              total cloud coverage (measured as a percentage of the sky) and present
              weather observations (standardised WMO codes that describe conditions
              like rain, fog, or thunderstorms).
            </p>
          </section>

          <section className="methodology-section">
            <h4>Station selection</h4>
            <p>
              For any location you search, we find the nearest active SMHI stations
              that record each type of data. Cloud coverage and lightning use
              <strong> independent station pools</strong> — a station that records
              cloud data may not record present weather, and vice versa. Stations are
              ranked by distance and selected adaptively: closer stations receive
              exponentially more weight (inverse distance squared), and very distant
              stations that would barely affect the result are dropped.
            </p>
          </section>

          <section className="methodology-section">
            <h4>Cloud coverage</h4>
            <p>
              Each selected station's historical cloud observations are averaged for
              the time period you're viewing (day of year, month, or calendar year).
              These per-station averages are then blended into a single estimate using
              the distance-based weights, so a station 10 km away counts roughly 100
              times more than one 100 km away. The dotted trend line uses LOESS
              (locally estimated scatterplot smoothing) to highlight the overall
              pattern without being distorted by individual data points.
            </p>
          </section>

          <section className="methodology-section">
            <h4>Lightning probability</h4>
            <p>
              Present weather observations are scanned for WMO codes that indicate
              thunderstorms or lightning. The probability shown is the fraction of
              all observations in each time period that reported a lightning-related
              code, blended across stations using the same distance weighting. The
              shaded band around the line is a <strong>95% Wilson score confidence
              interval</strong> — it shows the statistical uncertainty given the
              number of observations. When fewer than 30 observations exist for a
              time period, the confidence band is hidden because it would be
              misleadingly wide.
            </p>
          </section>

          <section className="methodology-section">
            <h4>Data quality</h4>
            <p>
              Each data type gets an independent quality assessment based on two
              factors: <strong>station coverage</strong> (how close the stations are
              and whether they surround the location or cluster in one direction)
              and <strong>historical data</strong> (how complete the record is and
              how many years of observations back up each average). The overall
              quality level shown is the worst factor across both cloud and lightning,
              so a limitation in either dimension is always surfaced.
            </p>
          </section>
        </div>
      </div>
    </div>
  )
}
