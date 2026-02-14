# Functional Specification — Cloud & Lightning Explorer

## Purpose

The Cloud & Lightning Explorer helps renewable energy companies assess the
climate conditions at a potential client's address before committing to a solar
panel installation. Given a street address, it answers: **How much sunlight
does this location typically get, and what is the lightning risk?** — broken
down by time of year, with data spanning decades of SMHI observations.

Cloud coverage is the primary factor in solar energy yield: a location with
consistently low cloud coverage will produce significantly more energy than a
heavily overcast one. Lightning probability indicates the risk of electrical
damage to rooftop installations and helps inform decisions about surge
protection, equipment specifications, and insurance requirements.

The app is not a forecast or an energy production calculator. It is a
**climate reference tool** — an early step in the site assessment process,
letting installers quickly screen a client's address before scheduling a
physical visit.

The UI prioritises **clarity**, **transparency**, **progressive disclosure**,
and **trustworthiness** — always making it clear what is measured data vs.
statistical estimates.

---

## Users

The primary user is a **solar energy company employee** (sales rep, site
assessor, or project planner) evaluating whether a potential client's property
is a good candidate for solar panel installation. They enter the client's
address to get a quick climate read before investing time in a full site visit.

Secondary users include the company's clients (homeowners) who may be shown the
tool as part of a sales consultation, as well as municipal energy planners
looking for location-level climate assessments.

No account, login, or prior knowledge of meteorology is required.

---

## User stories

### 1. Screen a client's address for solar potential

> As a solar installer, I want to enter a client's street address and see how
> cloudy their location is throughout the year, so I can quickly assess whether
> it's worth scheduling a site visit.

- The user types the client's address into a search field. After 3 characters,
  autocomplete suggestions appear via Nominatim. If nothing matches, the
  dropdown shows *"No results for '...'"*.
- The user selects a suggestion or presses Search.
- The app shows:
  - **Insight cards** summarising the key findings — e.g. *"Clearest: June
    (48%)"*, *"Cloudiest: December (81%)"* — giving an immediate sense of
    the seasonal sun/cloud balance.
  - A **cloud coverage bar chart** showing average cloud cover per month
    (default view). Lower bars mean more sunlight — better for solar.
  - A **LOESS trend line** on the cloud chart showing whether cloud conditions
    are improving or worsening over the observed period.
  - A **data quality badge** indicating how reliable the estimates are.
  - A collapsible **data sources drawer** showing which weather stations
    contribute to the estimate and how they are weighted.

### 2. Assess lightning risk for a rooftop installation

> As a solar installer, I want to see the probability of lightning at a client's
> location, so I can spec appropriate surge protection and factor risk into the
> project quote.

- When lightning data is available, a **lightning probability chart** appears
  below the cloud chart, showing how risk varies across the year.
- A **shaded confidence band** (95% Wilson score interval) shows how
  statistically reliable each probability estimate is.
- Tooltips show exact values:

  ```
  Lightning: 0.49%
  Confidence interval: 0.44% – 0.56%
  Data type: Measured
  ```

- Lightning values between 0% and 1% display as **"<1%"** for readability.
- When none of the nearby stations record lightning data, the chart is hidden
  and a notice explains the reason.

### 3. Compare seasonal patterns at different time scales

> As a user, I want to toggle between daily, monthly, and yearly views so I
> can see both seasonal detail and long-term trends.

| View    | What it shows                                              |
|---------|------------------------------------------------------------|
| **Daily** | 366 data points — one per calendar day, averaged across all years |
| **Monthly** (default) | 12 data points — one per month, averaged across all years |
| **Yearly** | One data point per year (e.g. 1952–2025) — long-term trends |

The toggle sits between the insight cards and the detailed charts. Switching
resolution triggers a **300ms crossfade animation** on the charts.

**Yearly view extras:**
- The LOESS trend curve highlights whether cloud cover has been increasing or
  decreasing over decades — useful for understanding whether solar viability
  at a location is improving.
- Insight cards update to show long-term trends (e.g. *"Cloud trend: Decreasing
  (66% → 55%)"*).

### 4. Understand data reliability

> As an installer advising a client, I want to know how trustworthy the climate
> data is for this address, so I can be transparent about the confidence level
> of my assessment.

The **data quality badge** uses a report-card model with four factors:

| Factor | What it measures |
|--------|-----------------|
| **Data coverage** | % of time buckets with any observations |
| **Observation depth** | Number of observations per bucket vs. expected baseline |
| **Station proximity** | Weighted average distance to contributing stations |
| **Directional coverage** | Angular spread of stations around the location |

Each factor is graded **good / fair / poor** with a colour-coded dot and
progress bar. The overall quality level (High / Medium / Low) equals the worst
individual factor — the weakest link determines confidence.

When overall quality is **"Low"**, a **warning banner** advises the user that
results may be less reliable and suggests trying a location closer to a weather
station.

### 5. Understand data gaps and estimates

> As a user, I want to know when the chart shows real observations vs.
> statistical fill-ins.

- Gaps are filled by linear interpolation.
- In the cloud bar chart, measured data has solid fill; estimated (interpolated)
  bars use a **faded fill with a dashed border**.
- Tooltips label each point as "Measured" or "Estimated".
- Confidence intervals on the lightning chart are suppressed when fewer than
  30 observations underlie a data point, preventing misleadingly wide bands.

### 6. Inspect the data sources

> As a user, I want to see exactly which weather stations are informing the
> estimate for my address, and how far away they are.

The **data sources drawer** (collapsed by default, with a **250ms slide
animation**) contains:
- A mini map with the searched location (pin) and stations (circles sized by
  weight).
- A table listing each station with distance (km) and weight (%).
- An explanation: *"Data is calculated using weighted averages from nearby
  weather stations. Closer stations contribute more to final values."*

### 7. Explore the full station network

> As an installer planning expansion into a new region, I want to browse all
> SMHI stations to understand the overall coverage of weather data across Sweden.

A separate **"All stations"** tab provides:
- Summary statistics: total stations, stations with cloud+lightning, cloud only.
- An interactive **map of Sweden** with all stations colour-coded by data
  capability (green = cloud + lightning, amber = cloud only).
- A searchable, filterable table of every station with coordinates and data
  flags.
- Filters by capability and a name search that updates both the table and map.

---

## User journeys

### Journey A — "New lead in Malmö — quick screening"

1. A sales rep receives an enquiry from a homeowner in Malmö. They open the
   app and type the client's street address.
2. Selects from autocomplete suggestions.
3. Insight cards read: *"Clearest: June (48%)"*, *"Cloudiest: December (79%)"*,
   *"Lightning peak: July (1.2%)"*.
4. The monthly cloud bar chart shows a clear summer dip — June through August
   have the lowest cloud coverage, meaning the best solar yield.
5. The lightning chart shows a modest summer peak, well under 2% — no
   unusual risk that would require special equipment.
6. Data quality badge shows "High" — confident in the estimate.
7. The rep notes the findings and schedules a site visit, knowing the climate
   data supports a viable installation.

### Journey B — "Comparing two client addresses in the pipeline"

1. An assessor has two pending leads: one in Gothenburg, one in Sundsvall.
2. They search the Gothenburg address first, note the key insights and
   switch to the yearly view. Cloud cover has been gradually decreasing over
   30 years — a positive trend for solar.
3. They search the Sundsvall address next. Higher year-round cloud coverage
   but very low lightning risk.
4. They use the comparison to prioritise the Gothenburg lead, where the
   climate data is more favourable, while flagging Sundsvall as viable but
   with lower expected yield.

### Journey C — "Client in a remote location near the Norwegian border"

1. An assessor searches for a client's rural property in western Sweden.
2. Charts load, but the data quality badge shows "Low" with poor station
   proximity and poor directional coverage (all stations are to the east).
3. A warning banner appears explaining that results may be less reliable.
4. The assessor expands the data sources drawer and sees that the nearest
   station is 120 km away. They understand the estimate is rough.
5. They note in the client file that a physical site visit with on-site
   irradiance measurement is essential — the climate tool alone isn't
   sufficient for this location.

### Journey D — "Scoping a new service region in Norrbotten"

1. A project planner is evaluating whether to expand the company's service
   area into Norrbotten. They open the "All stations" tab.
2. The map shows sparse station coverage in inland areas, with most stations
   along the coast.
3. They filter to "Cloud + Lightning" to see which areas have full data.
4. They search for a specific town, note the nearest stations, and search
   that address on the main page to check cloud patterns.
5. They use the yearly view to check the LOESS trend — cloud cover has been
   stable, not worsening. Combined with the midnight sun effect in summer,
   they decide the region is worth exploring further.

### Journey E — "Client site with no lightning data"

1. An assessor searches for a client's address in northern Sweden.
2. The cloud chart loads normally, but the lightning chart is absent.
3. A notice explains that no nearby stations record lightning observations.
4. The assessor notes they'll need a separate source for lightning risk
   assessment (e.g. SMHI's lightning location data) and proceeds with the
   cloud coverage data for the initial evaluation.

---

## Data sources

| Source | What it provides | Usage terms |
|--------|-----------------|-------------|
| **SMHI Open Data (Metobs)** | Historical weather observations from ~100+ Swedish stations. Parameters: cloud coverage (param 16), present weather / WMO codes (param 13). | Free, open data. |
| **Nominatim (OpenStreetMap)** | Geocoding and autocomplete. | Free with attribution; rate-limited. |
| **OpenStreetMap tile servers** | Map tiles for the station map. | Free with attribution. |

---

## What the app does NOT do

- **It is not a weather forecast.** It shows historical averages over decades.
- **It is not an energy yield calculator.** It does not estimate kWh output —
  that requires panel specs, roof angle, shading analysis, etc.
- **It does not replace a physical site assessment.** It is a screening tool
  to inform go/no-go decisions before committing to a visit.
- **It does not cover locations outside Sweden.**
- **It only shows cloud coverage and lightning probability** — not temperature,
  precipitation, wind, solar irradiance, or other parameters.
- **It does not require an account or store any user data.**

---

## Accessibility

- **Keyboard navigation:** Both chart panels are focusable (`tabIndex`).
  Users can press **Left/Right arrow keys** to step through data points and
  **Escape** to clear. Focus is indicated with a visible border highlight.
- **Colorblind safety:** The cloud (blue) and lightning (amber) channels are
  perceptually distant under protanopia, deuteranopia, and tritanopia. The
  data quality badge uses both colour and a **distinct symbol** (checkmark,
  circle, warning triangle) so levels are identifiable without colour alone.
- **Contrast:** All secondary text colours have been verified to meet WCAG AA
  minimum contrast ratios (4.5:1 for normal text) against the dark background.
- **Screen reader hints:** Chart panels have `role="img"` with descriptive
  `aria-label` attributes. The quality badge uses `role="status"`. The
  drawer toggle uses `aria-expanded`.
