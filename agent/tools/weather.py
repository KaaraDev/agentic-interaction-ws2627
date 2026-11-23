"""Weather tool: the forecast for one city and day from {DATA_BASE_URL}/weather/{city}/{YYYY-MM-DD}.json."""
from .base import Tool
from .data import CITIES, city_slug, fetch_json, iso_day, to_json

NAME = 'get_weather'


def weather_tool(data_base_url: str) -> Tool:
    def get_weather(city: str, day: str) -> str:
        city, day = city_slug(city), iso_day(day)
        data = fetch_json(data_base_url, f"weather/{city}/{day}.json")
        if data is None:
            # Lecture 3: a 404 read as "no rain". Say plainly that there is no forecast at all.
            return to_json({"city": city, "date": day, "available": False,
                            "note": "No weather data for this city and day. Do not guess the weather."})
        return to_json(_compact(data, city, day))

    return Tool(
        name=NAME,
        description=("Weather forecast for one city and one day: condition, temperature, rain probability "
                     "and wind. If the result says there is no data, there is no forecast for that city and "
                     "day; never assume dry weather. For several cities or days, call it for all of them "
                     "in the same reply."),
        parameters={
            "type": "object",
            "properties": {
                "city": {"type": "string", "enum": list(CITIES),
                         "description": "City slug: 'ulm' or 'muenchen' (Munich)."},
                "day": {"type": "string",
                        "description": "The day in ISO format YYYY-MM-DD, e.g. 2026-10-29."},
            },
            "required": ["city", "day"],
        },
        func=get_weather,
    )


def _compact(data, city: str, day: str) -> dict:
    if not isinstance(data, dict):
        return {"city": city, "date": day, "forecast": data}
    result = {"city": city, "date": day, "available": True}
    for key in ('condition', 'temp_c', 'wind_kmh'):
        if data.get(key) not in (None, ''):
            result[key] = data[key]
    rain = data.get('rain_probability')
    if isinstance(rain, (int, float)):
        # 0.6 -> "60%": the model then quotes the value instead of converting it itself
        result['rain_probability'] = f"{round(rain * 100) if rain <= 1 else round(rain)}%"
    return result
