"""Access to the mock data under DATA_BASE_URL, shared by all tools.

iso_day()     validates a day argument (YYYY-MM-DD)
city_slug()   maps a city argument to the slug the data uses (ulm, muenchen)
fetch_json()  one GET request; HTTP 404 means "no data" and returns None
"""
import json
import urllib.error
import urllib.request
from datetime import date

from ..errors import ToolError

CITIES = ('ulm', 'muenchen')
# Names a model is likely to use instead of the slug. 'munich' -> 404 is the failure from lecture 3.
_CITY_ALIASES = {'munich': 'muenchen', 'münchen': 'muenchen', 'munchen': 'muenchen', 'muenich': 'muenchen'}


def iso_day(value) -> str:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (TypeError, ValueError):
        raise ToolError(f"Invalid date {value!r}, expected YYYY-MM-DD.") from None


def city_slug(value) -> str:
    name = str(value or '').strip().lower()
    slug = _CITY_ALIASES.get(name, name)
    if slug not in CITIES:
        raise ToolError(f"Unknown city {value!r}. Known cities: {', '.join(CITIES)}.")
    return slug


def known_city(value) -> str | None:
    """The slug, or None for a city the mock data has no data for (e.g. 'berlin')."""
    try:
        return city_slug(value)
    except ToolError:
        return None


def unknown_city_result(city, day: str) -> str:
    """A city without data is "no data for this place", like a 404: a valid result, so the run treats
    the day as looked up and the model says there is no data instead of retrying or guessing."""
    return to_json({"city": str(city), "date": day, "available": False,
                    "note": f"No data for {city!r}: only {', '.join(CITIES)} are known. Do not guess."})


def fetch_json(data_base_url: str, path: str):
    """The parsed JSON at {data_base_url}/{path}; None if the endpoint has no data (HTTP 404)."""
    url = f"{data_base_url}/{path}"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            text = response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        if e.code == 404:  # no data: a valid result, not an error
            return None
        raise ToolError(f"HTTP {e.code} while reading {url}") from None
    except Exception as e:
        raise ToolError(f"{type(e).__name__} while reading {url}: {e}") from None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise ToolError(f"Response from {url} is not valid JSON") from None


def to_json(data) -> str:
    """Compact JSON for the model: every character is sent again with each later step."""
    return json.dumps(data, ensure_ascii=False, separators=(',', ':'))
