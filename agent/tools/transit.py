"""Train connections tool: {DATA_BASE_URL}/transit/{from}/{to}/{YYYY-MM-DD}.json.

Every connection is checked against the calendar of the same day in code (tools/schedule.py), so
the model reports a computed result instead of comparing times itself.
"""
from ..errors import ToolError
from .base import Tool
from .data import CITIES, fetch_json, iso_day, known_city, to_json, unknown_city_result
from .schedule import check_connection

NAME = 'get_connections'


def _calendar(data_base_url: str, day: str):
    """(events or None, note for the model)."""
    try:
        data = fetch_json(data_base_url, f"calendar/{day}.json")
    except ToolError as e:
        return None, f"not checked against the calendar ({e})"
    if data is None:
        return [], "no calendar data for this day: nothing to check against"
    events = data.get('events') if isinstance(data, dict) else None
    if not isinstance(events, list):
        return None, "not checked against the calendar (unexpected calendar format)"
    return events, f"checked against {len(events)} appointment(s) of this day"


def _trains_back(data_base_url: str, day: str):
    """Lookup for the calendar check: connections from -> to on `day`, None if there is no data.
    Cached, so several connections needing the same trip back cost one request."""
    cache = {}

    def lookup(from_city: str, to_city: str):
        if (from_city, to_city) not in cache:
            try:
                data = fetch_json(data_base_url, f"transit/{from_city}/{to_city}/{day}.json")
            except ToolError:
                data = None
            connections = data.get('connections') if isinstance(data, dict) else None
            cache[(from_city, to_city)] = connections if isinstance(connections, list) else None
        return cache[(from_city, to_city)]

    return lookup


def _summary(check: dict) -> dict:
    """Only non-empty fields, to keep the result short (it is sent again with every step)."""
    return {key: value for key, value in check.items() if value not in ([], None) or key == 'fits'}


def transit_tool(data_base_url: str) -> Tool:
    # 'origin' / 'destination' instead of 'from' / 'to': 'from' is a Python keyword.
    def get_connections(origin: str, destination: str, day: str) -> str:
        day = iso_day(day)
        for city in (origin, destination):
            if known_city(city) is None:
                return unknown_city_result(city, day)
        origin, destination = known_city(origin), known_city(destination)
        if origin == destination:
            raise ToolError("origin and destination are the same city.")
        data = fetch_json(data_base_url, f"transit/{origin}/{destination}/{day}.json")
        if data is None:
            return to_json({"from": origin, "to": destination, "date": day, "available": False,
                            "note": "No train connection data for this route and day. Do not invent trains."})
        connections = data.get('connections') if isinstance(data, dict) else None
        if not isinstance(connections, list):
            return to_json(data)
        result = {"from": origin, "to": destination, "date": day, "available": True}
        events, calendar_note = _calendar(data_base_url, day)
        if events is None:
            result["calendar_check"] = calendar_note
            result["connections"] = connections
        else:
            result["calendar_check"] = calendar_note
            trains_back = _trains_back(data_base_url, day)
            result["connections"] = [{**c, "check": _summary(check_connection(c, origin, destination, events,
                                                                             trains_back))}
                                     for c in connections if isinstance(c, dict)]
            fitting = [c["train"] for c in result["connections"] if c["check"]["fits"]]
            result["fitting_trains"] = fitting or "none: every connection conflicts with an appointment"
        return to_json(result)

    return Tool(
        name=NAME,
        description=("Train connections between two cities on one day: departure, arrival, number of "
                     "changes, train and price. Each connection is already checked against the user's "
                     "calendar of that day ('check': fits, conflicts, warnings); report that result, do not "
                     "redo the check. Read-only: it cannot book tickets. If the result says there is no data, "
                     "there are no known connections for that route and day; never invent trains."),
        parameters={
            "type": "object",
            "properties": {
                "origin": {"type": "string", "enum": list(CITIES),
                           "description": "Departure city slug: 'ulm' or 'muenchen' (Munich)."},
                "destination": {"type": "string", "enum": list(CITIES),
                                "description": "Arrival city slug: 'ulm' or 'muenchen' (Munich)."},
                "day": {"type": "string",
                        "description": "The day of travel in ISO format YYYY-MM-DD, e.g. 2026-10-29."},
            },
            "required": ["origin", "destination", "day"],
        },
        func=get_connections,
    )
