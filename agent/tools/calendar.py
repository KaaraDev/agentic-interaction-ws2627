"""Calendar tool: the appointments of one day from {DATA_BASE_URL}/calendar/{YYYY-MM-DD}.json."""
import json
import urllib.error
import urllib.request
from datetime import date

from ..errors import ToolError
from .base import Tool

NAME = 'get_calendar_day'


def calendar_tool(data_base_url: str) -> Tool:
    def get_calendar_day(day: str) -> str:
        try:
            day = date.fromisoformat(day).isoformat()
        except (TypeError, ValueError):
            raise ToolError(f"Invalid date {day!r}, expected YYYY-MM-DD.") from None
        url = f"{data_base_url}/calendar/{day}.json"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                text = response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            if e.code == 404:  # no data for this day: a valid result, not an error
                return json.dumps({"date": day, "events": [], "note": "No calendar data for this day."})
            raise ToolError(f"HTTP {e.code} while reading {url}") from None
        except Exception as e:
            raise ToolError(f"{type(e).__name__} while reading {url}: {e}") from None
        try:  # minify: the pretty-printed file wastes about a third of the tokens
            return json.dumps(json.loads(text), ensure_ascii=False, separators=(',', ':'))
        except json.JSONDecodeError:
            return text

    return Tool(
        name=NAME,
        description=("Returns the calendar appointments of the user for exactly one day "
                     "(title, start and end time, location, all-day flag). "
                     "Call it once per day the user asks about."),
        parameters={
            "type": "object",
            "properties": {
                "day": {"type": "string",
                        "description": "The day to look up in ISO format YYYY-MM-DD, e.g. 2026-10-29."}
            },
            "required": ["day"],
        },
        func=get_calendar_day,
    )


def fetched_days(results) -> set[str]:
    """ISO dates whose calendar data was fetched successfully (a 404 'no data' counts as fetched)."""
    days = set()
    for result in results:
        if result.tool == NAME and result.ok:
            try:
                days.add(date.fromisoformat(str(result.args.get('day'))).isoformat())
            except ValueError:
                pass
    return days
