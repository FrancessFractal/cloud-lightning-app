# Functional Specification — Weather App

## Purpose

The Weather App helps people understand the historical climate patterns of any
location in Sweden. Given an address, it answers the questions: **How cloudy is
it here, and how likely is lightning?** — broken down by time of year, with
data spanning decades of SMHI observations.

It is not a forecast tool. It is a climate reference tool — useful for someone
deciding where to move, planning seasonal activities, or simply curious about
long-term weather trends at a specific place.

---

## Users

The app is designed for a general Swedish audience — anyone who can type an
address and read a chart. No account, login, or prior knowledge of meteorology
is required.

---

## User stories

### 1. Look up climate patterns for a location

> As a user, I want to enter an address or city name and immediately see cloud
> coverage and lightning probability for that place, so I can understand its
> typical weather throughout the year.

**How it works today:**

- The user types into a search field. After 3 characters, suggestions appear
  in a dropdown (autocomplete), narrowing as they type. If nothing matches,
  the dropdown shows *"No results for '...'"* instead of silently stalling.
- The user selects a suggestion (click or keyboard) or presses Search.
- The app shows:
  - A **plain-language summary** sentence at the top of the chart card,
    e.g. *"Clearest in June (52%). Cloudiest in December (79%). Lightning
    peaks in July at 2.1%."* — so the user gets the answer without having
    to study the chart.
  - A **chart** with two data series:
    - **Cloud coverage** (bar chart, left axis, 0–100%)
    - **Lightning probability** (line chart, right axis, %)
  - An **interactive map** showing the searched location (pin marker) and
    each contributing SMHI station (circle markers sized by weight). Hovering
    a station shows its name, distance, and weight percentage.
  - A **station list** below the chart naming the contributing stations with
    their distance and weight.

**Key detail:** The data is not from a single weather station. The app finds
the nearest stations, weights them by proximity (closer stations matter more),
and blends their data into a single estimate for the exact location. The user
sees a smooth, location-specific result rather than having to pick a station
themselves.

### 2. Change the time resolution

> As a user, I want to toggle between daily, monthly, and yearly views so I
> can see both seasonal patterns and long-term trends.

**Three resolutions:**

| View    | What it shows                                              | Typical use                          |
|---------|------------------------------------------------------------|--------------------------------------|
| **Day** | 366 data points — one per calendar day, averaged across all years | Fine-grained seasonal patterns. "Is mid-June cloudier than early June?" |
| **Month** (default) | 12 data points — one per month, averaged across all years | The standard overview. "Which months are sunniest?" |
| **Year** | One data point per year (e.g. 1952–2025)                  | Long-term trends. "Is it getting cloudier over the decades?" |

The user switches via Day / Month / Year buttons above the chart. The chart
re-fetches data for the new resolution instantly (or with a brief loading
state for first-time lookups).

**Yearly view extras:**

- A **trend line** (dashed) is overlaid on the yearly bar chart, computed
  via linear regression over the real (non-interpolated) data points. This
  makes it immediately visible whether cloud coverage is increasing,
  decreasing, or stable over the decades.
- The plain-language summary adapts for yearly data, e.g. *"Cloud coverage
  has decreased from ~66% in the 1950s to ~55% in the 2020s."*

### 3. Understand data gaps

> As a user, I want to know when the chart is showing real observations vs.
> estimates, so I don't mistake missing data for actual weather.

Some stations have gaps — years where no observations were recorded. When this
happens:

- The gap is filled by **linear interpolation** (a smooth line between the
  nearest real data points on either side).
- Interpolated bars appear **faded** with a dashed border, visually distinct
  from real data.
- A notice banner explains what the faded bars mean.
- Hovering an interpolated point shows *"(estimated) — No observations,
  interpolated from neighbours"* in the tooltip.

### 4. Understand lightning data availability

> As a user, I want to know if lightning data is available for my location, so
> I'm not confused by a missing chart line.

Not all SMHI stations record "present weather" observations (the parameter
that includes lightning/thunder codes). When none of the nearby stations have
this data:

- The lightning line and right-hand axis are hidden entirely.
- A notice explains: *"None of the nearby stations record present weather
  observations, so lightning data is not available."*

### 5. Explore all SMHI stations

> As a user, I want to browse all available weather stations and see what data
> each one collects, so I can understand the coverage of the observation
> network.

A separate "All stations" tab shows:

- **Summary stats:** total stations, how many collect both cloud + lightning,
  how many collect cloud only.
- **Searchable table** of every active station with: name, ID, coordinates,
  and Yes/No badges for cloud data and lightning data.
- **Filters** to narrow by data capability (All / Cloud + Lightning / Cloud
  only).

### 6. See where the data comes from on a map

> As a user, I want to see the spatial relationship between my location and the
> contributing weather stations, so I can judge how representative the estimate
> is.

After a search, an interactive map appears below the chart showing:

- A **pin marker** for the searched location.
- **Circle markers** for each contributing SMHI station, sized proportionally
  to their weight in the blend.
- Hovering a station circle shows its name, distance (km), and weight (%).
- The map auto-zooms to fit all markers.

---

## User journeys

### Journey A — "Should I move to Visby?"

1. User opens the app, types "Visby" in the search box.
2. Autocomplete shows suggestions; user selects "Visby, Gotlands kommun,
   Gotlands län, Sverige".
3. The monthly chart loads. A summary sentence reads: *"Clearest in July
   (50%). Cloudiest in December (81%). Lightning peaks in July at 1.8%."*
4. Below the chart, a map shows the pin at Visby and two station circles on
   Gotland and the mainland. The user can see how close the stations are.
5. User clicks **Year** to check long-term trends. A dashed trend line shows
   cloud coverage has been roughly stable. The summary confirms: *"Cloud
   coverage has remained roughly stable from ~62% in the 1960s to ~58% in the
   2020s."*
6. User clicks **Day** to find the precise sunniest window — late June shows
   a consistent dip in cloudiness.

### Journey B — "Why does my location show no lightning?"

1. User searches for a rural location in northern Sweden.
2. The chart loads but only shows cloud coverage — no lightning line.
3. User reads the notice: *"None of the nearby stations record present weather
   observations, so lightning data is not available."*
4. Curious, user clicks the "All stations" tab and filters to "Cloud +
   Lightning" to see which stations do record it. They discover the nearest
   one is far away.

### Journey C — "What's this gap in the yearly chart?"

1. User searches for "Årsta" and switches to the Year view.
2. Most years show solid blue bars, but 2006–2007 appear faded with dashed
   borders. The trend line passes smoothly through the gap.
3. User hovers over 2006 and reads: *"(estimated) — No observations,
   interpolated from neighbours."*
4. The interpolation notice at the top of the chart confirms: *"Faded bars
   indicate periods with no station data — values are estimated."*

### Journey D — "I typed something wrong"

1. User types "Stokholm" (misspelled) in the search box.
2. Autocomplete shows *"No results for 'Stokholm'"* — immediately signalling
   the typo rather than silently showing stale results.
3. User corrects to "Stockholm" and valid suggestions appear.

---

## Data sources

| Source | What it provides | Usage terms |
|--------|-----------------|-------------|
| **SMHI Open Data (Metobs)** | Historical weather observations from ~100+ Swedish stations. Parameters used: cloud coverage (param 16) and present weather / WMO codes (param 13). | Free, open data. |
| **Nominatim (OpenStreetMap)** | Geocoding — converts addresses to coordinates. Powers the autocomplete and search. | Free with attribution; rate-limited. |
| **OpenStreetMap tile servers** | Map tiles for the interactive station map. | Free with attribution. |

---

## What the app does NOT do

- **It is not a weather forecast.** It shows historical averages, not
  predictions.
- **It does not cover locations outside Sweden.** The data source is SMHI
  and the geocoder is biased toward Swedish addresses.
- **It does not show precipitation, temperature, wind, or other parameters.**
  Only cloud coverage and lightning probability.
- **It does not require an account or store any user data.**
