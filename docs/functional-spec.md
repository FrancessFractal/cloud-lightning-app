# Functional Specification — Cloud & Lightning Explorer

## Purpose

The Cloud & Lightning Explorer helps people understand the historical climate
patterns of any location in Sweden. Given an address, it answers the questions:
**How cloudy is it here, and how likely is lightning?** — broken down by time
of year, with data spanning decades of SMHI observations.

It is not a forecast tool. It is a climate reference tool — useful for someone
deciding where to move, planning seasonal activities, or simply curious about
long-term weather trends at a specific place.

The UI prioritizes **clarity**, **transparency**, **progressive disclosure**,
and **trustworthiness** — always making it clear what is measured data vs.
statistical estimates.

---

## Users

The app is designed for a general Swedish audience — anyone who can type an
address and read a chart. No account, login, or prior knowledge of meteorology
is required.

---

## Page layout

After a successful search, the page is structured as follows:

```
Location Search / Header
  Address input with autocomplete

Annual Summary Section
  Cloud area chart (compact, yearly)
  Lightning line chart (compact, yearly)

Insight Cards Row
  Auto-generated cards: clearest period, cloudiest period, lightning peak, etc.

Granularity Toggle: Daily | Monthly | Yearly

Detailed Cloud Chart Panel
  Area chart, full height

Detailed Lightning Chart Panel
  Line chart + confidence band, full height

Data Confidence Badge
  "Data Confidence: High — 92% Measured | 8% Estimated"

Data Sources Drawer (collapsed by default)
  Mini map with station markers
  Station table: name, distance, weight
  Explanation text
```

---

## User stories

### 1. Look up climate patterns for a location

> As a user, I want to enter an address or city name and immediately see cloud
> coverage and lightning probability for that place.

- The user types into a search field. After 3 characters, suggestions appear.
  If nothing matches, the dropdown shows *"No results for '...'"*.
- The user selects a suggestion or presses Search.
- The app shows:
  - An **annual summary** (always-visible yearly overview) with compact cloud
    and lightning charts.
  - **Insight cards** — auto-generated from the data: *"Cloudiest: November
    (76%)"*, *"Lightning peak: July (18%)"*, etc.
  - **Detailed charts** — a cloud area chart and a lightning line chart, split
    into separate vertically stacked panels with independent Y-axes.
  - A **data confidence badge** showing the ratio of measured to estimated
    data.
  - A collapsible **data sources drawer** with a map and station table.

### 2. Change the time resolution

> As a user, I want to toggle between daily, monthly, and yearly views so I
> can see both seasonal patterns and long-term trends.

| View    | What it shows                                              |
|---------|------------------------------------------------------------|
| **Daily** | 366 data points — one per calendar day, averaged across all years |
| **Monthly** (default) | 12 data points — one per month, averaged across all years |
| **Yearly** | One data point per year (e.g. 1952–2025) |

The toggle is centered between the insight cards and the detailed charts.
Switching resolution triggers a **300ms crossfade animation** on the detail
charts. The annual summary always shows yearly data regardless of the selected
resolution.

**Yearly view extras:**
- A LOESS trend curve is overlaid on the cloud area chart.
- Insight cards summarize long-term trends (e.g. "Cloud trend: Decreasing
  (66% → 55%)").

### 3. See confidence intervals

> As a user, I want to see how confident the lightning estimate is, so I can
> judge whether the probabilities are meaningful.

The lightning chart panel displays a **shaded confidence band** between the
upper and lower bounds of a 95% Wilson score interval. Tooltips show the
exact interval for each data point:

```
Lightning: 0.49%
Confidence interval: 0.44% – 0.56%
Data type: Measured
```

Lightning values between 0% and 1% are displayed as **"<1%"** in tooltips
and insight cards for readability.

### 4. Understand data gaps

> As a user, I want to know when the chart is showing real observations vs.
> estimates.

- Gaps are filled by linear interpolation.
- In the cloud area chart, measured data has a solid fill; estimated
  (interpolated) segments use a **hatched SVG pattern** overlay, with a
  legend swatch in the panel header.
- Tooltips indicate whether a point is "Measured" or "Estimated".
- The **data confidence badge** always shows the measured/estimated ratio with
  a color-coded level and symbol: green checkmark (High, >85%), amber circle
  (Medium, 60-85%), red warning (Low, <60%).
- When more than 40% of the data is estimated (measured < 60%), a **warning
  banner** appears beneath the badge explaining the situation and suggesting
  the user try a location closer to a weather station.

### 5. Understand lightning data availability

> As a user, I want to know if lightning data is available for my location.

When none of the nearby stations have lightning data:
- The lightning chart panel is hidden entirely.
- A notice explains the reason.

### 6. See where the data comes from

> As a user, I want to see the spatial relationship between my location and the
> contributing stations.

The **data sources drawer** (collapsed by default, with a **250ms slide
animation** on expand/collapse) contains:
- A mini map with the searched location (pin) and stations (circles sized by
  weight).
- A table listing each station with distance and weight percentage.
- An explanation: *"Data is calculated using weighted averages from nearby
  weather stations. Closer stations contribute more to final values."*

### 7. Explore all SMHI stations

A separate "All stations" tab shows a searchable, filterable table of every
active SMHI station with their data capabilities.

---

## User journeys

### Journey A — "Should I move to Visby?"

1. User opens the app, types "Visby".
2. Selects from autocomplete suggestions.
3. The annual summary shows long-term yearly trends at a glance.
4. Insight cards read: *"Clearest July (50%)"*, *"Cloudiest December (81%)"*,
   *"Lightning peak July (1.8%)"*.
5. The monthly detail charts show the seasonal pattern with cloud area and
   lightning line + confidence band.
6. The data confidence badge shows "High — 100% Measured".
7. User expands the data sources drawer to see the stations on a map.
8. User clicks **Yearly** to see the LOESS trend curve. Insight cards update
   to show the long-term direction.

### Journey B — "Why does my location show no lightning?"

1. User searches for a rural northern location.
2. Charts load; the lightning panel is absent.
3. A notice explains that no nearby stations record lightning data.
4. User opens the "All stations" tab to explore which stations have lightning
   data.

### Journey C — "How confident is this data?"

1. User searches for "Årsta" and switches to Yearly view.
2. The data confidence badge shows "Medium — 72% Measured".
3. Tooltips on individual bars show "Estimated" for the gap years.
4. The lightning confidence band is wider in years with fewer observations,
   narrower in years with many.

### Journey D — "I typed something wrong"

1. User types "Stokholm" (misspelled).
2. Autocomplete shows *"No results for 'Stokholm'"*.
3. User corrects to "Stockholm" and valid suggestions appear.

---

## Data sources

| Source | What it provides | Usage terms |
|--------|-----------------|-------------|
| **SMHI Open Data (Metobs)** | Historical weather observations from ~100+ Swedish stations. Parameters: cloud coverage (param 16), present weather / WMO codes (param 13). | Free, open data. |
| **Nominatim (OpenStreetMap)** | Geocoding and autocomplete. | Free with attribution; rate-limited. |
| **OpenStreetMap tile servers** | Map tiles for the station map. | Free with attribution. |

---

## What the app does NOT do

- **It is not a weather forecast.** It shows historical averages.
- **It does not cover locations outside Sweden.**
- **It only shows cloud coverage and lightning probability** — not
  temperature, precipitation, wind, etc.
- **It does not require an account or store any user data.**

---

## Accessibility

- **Keyboard navigation:** Both chart panels are focusable (`tabIndex`).
  Users can press **Left/Right arrow keys** to step through data points and
  **Escape** to clear. Focus is indicated with a visible border highlight.
- **Colorblind safety:** The cloud (blue) and lightning (amber) channels are
  perceptually distant under protanopia, deuteranopia, and tritanopia. The
  confidence badge uses both color and a **distinct symbol** (checkmark,
  circle, warning triangle) so levels are identifiable without color alone.
- **Contrast:** All secondary text colors have been verified to meet WCAG AA
  minimum contrast ratios (4.5:1 for normal text) against the dark background.
- **Screen reader hints:** Chart panels have `role="img"` with descriptive
  `aria-label` attributes. The confidence badge uses `role="status"`. The
  drawer toggle uses `aria-expanded`.

---

## Animations

| Interaction | Duration | Easing | Notes |
|-------------|----------|--------|-------|
| Granularity toggle | 300ms | ease | Opacity crossfade on detail charts |
| Drawer expand/collapse | 250ms | ease | max-height slide + chevron rotation |
| Chevron rotation | 200ms | ease | CSS transform on `.drawer-chevron` |
