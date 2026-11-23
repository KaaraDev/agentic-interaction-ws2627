# Tool fact sheet

All tools read the mock data under `DATA_BASE_URL` with HTTP GET. None of them changes anything, so
each is idempotent (calling it twice has the same effect as once), may be retried automatically,
and runs without asking (see `DELEGATION.md`, actions 1–3).

| Tool | Endpoint | Arguments | Returns | No data (HTTP 404) | Effect | Reversible |
|---|---|---|---|---|---|---|
| `get_calendar_day` | `calendar/{day}.json` | `day` (YYYY-MM-DD) | appointments: title, start, end, location, all-day flag | empty list + "No calendar data for this day." | read only, nothing changes | yes — nothing to undo |
| `get_weather` | `weather/{city}/{day}.json` | `city` (`ulm`, `muenchen`), `day` | condition, temperature °C, rain probability %, wind km/h | `available: false` + "No weather data … Do not guess the weather." | read only, nothing changes | yes — nothing to undo |
| `get_connections` | `transit/{origin}/{destination}/{day}.json` | `origin`, `destination` (`ulm`, `muenchen`), `day` | departure, arrival, changes, train, price € | `available: false` + "No train connection data … Do not invent trains." | read only, nothing changes; cannot book | yes — nothing to undo |

Errors that are not "no data" (invalid date, unknown city, same origin and destination, HTTP 5xx,
network) come back to the model as an `{"error": ...}` result; the run goes on.
