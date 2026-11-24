# Tool fact sheet

All tools read the mock data under `DATA_BASE_URL` with HTTP GET. None of them changes anything, so
each is idempotent (calling it twice has the same effect as once), may be retried automatically,
and runs without asking (see `DELEGATION.md`, actions 1–3).

| Tool | Endpoint | Arguments | Returns | No data (HTTP 404) | Effect | Reversible |
|---|---|---|---|---|---|---|
| `get_calendar_day` | `calendar/{day}.json` | `day` (YYYY-MM-DD) | appointments: title, start, end, location, all-day flag | empty list + "No calendar data for this day." | read only, nothing changes | yes — nothing to undo |
| `get_weather` | `weather/{city}/{day}.json` | `city` (`ulm`, `muenchen`), `day` | condition, temperature °C, rain probability %, wind km/h | `available: false` + "No weather data … Do not guess the weather." | read only, nothing changes | yes — nothing to undo |
| `get_connections` | `transit/{origin}/{destination}/{day}.json` (+ `calendar/{day}.json` for the check) | `origin`, `destination` (`ulm`, `muenchen`), `day` | departure, arrival, changes, train, price €, and per connection a calendar `check` (fits, conflicts, warnings, notes) plus `fitting_trains` | `available: false` + "No train connection data … Do not invent trains." | read only, nothing changes; cannot book | yes — nothing to undo |

A city without data (e.g. `berlin`) gets an `available: false` "no data for this city" result.
Other errors (invalid date, same origin and destination, HTTP 5xx, network) come back to the model
as an `{"error": ...}` result; the run goes on.

## Calendar check of a connection (`agent/tools/schedule.py`)

Computed in code, because the model compares times and places unreliably. Appointment places come
from the location text: `Muenchen`/`München`/`Munich` → muenchen, `Ulm` or a university room such as
`O27/3302` → ulm, `online` (or empty) → online, anything else → unknown.

| Situation | Result |
|---|---|
| an in-person appointment overlaps the journey | conflict |
| the last in-person appointment before departure is in another city | conflict |
| the next in-person appointment after arrival is in another city and starts sooner than the trip back could take (the journey's own duration) | conflict (you would miss it) |
| … and starts later | warning: a trip back is needed |
| an online appointment overlaps the journey | warning: join from the train |
| the next in-person appointment is at the destination | note: arrives N min before it |
