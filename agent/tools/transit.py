"""Train connections tool: {DATA_BASE_URL}/transit/{from}/{to}/{YYYY-MM-DD}.json."""
from ..errors import ToolError
from .base import Tool
from .data import CITIES, city_slug, fetch_json, iso_day, to_json

NAME = 'get_connections'


def transit_tool(data_base_url: str) -> Tool:
    # 'origin' / 'destination' instead of 'from' / 'to': 'from' is a Python keyword.
    def get_connections(origin: str, destination: str, day: str) -> str:
        origin, destination, day = city_slug(origin), city_slug(destination), iso_day(day)
        if origin == destination:
            raise ToolError("origin and destination are the same city.")
        data = fetch_json(data_base_url, f"transit/{origin}/{destination}/{day}.json")
        if data is None:
            return to_json({"from": origin, "to": destination, "date": day, "available": False,
                            "note": "No train connection data for this route and day. Do not invent trains."})
        connections = data.get('connections') if isinstance(data, dict) else None
        if not isinstance(connections, list):
            return to_json(data)
        return to_json({"from": origin, "to": destination, "date": day, "available": True,
                        "connections": connections})

    return Tool(
        name=NAME,
        description=("Train connections between two cities on one day: departure, arrival, number of "
                     "changes, train and price. Read-only: it cannot book tickets. If the result says there "
                     "is no data, there are no known connections for that route and day; never invent trains."),
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
