"""Calendar tool: the appointments of one day from {DATA_BASE_URL}/calendar/{YYYY-MM-DD}.json."""
from .base import Tool
from .data import fetch_json, iso_day, to_json

NAME = 'get_calendar_day'


def calendar_tool(data_base_url: str) -> Tool:
    def get_calendar_day(day: str) -> str:
        day = iso_day(day)
        data = fetch_json(data_base_url, f"calendar/{day}.json")
        if data is None:
            return to_json({"date": day, "events": [], "note": "No calendar data for this day."})
        return to_json(_compact(data))

    return Tool(
        name=NAME,
        description=("Returns the calendar appointments of the user for exactly one day "
                     "(title, start and end time, location, all-day flag). "
                     "For several days, call it for all of them in the same reply."),
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


def _compact(data):
    """Only what the answer needs. The whole history is sent again with every step, so every
    field that is left out here is saved many times: no ids, no date repeated in every event,
    no empty values, all_day only when true."""
    if not isinstance(data, dict) or not isinstance(data.get('events'), list):
        return data
    events = []
    for event in data['events']:
        if not isinstance(event, dict):
            events.append(event)
            continue
        events.append({key: value for key, value in event.items()
                       if key not in ('id', 'date') and value not in (None, '', False)})
    return {**data, 'events': events}
