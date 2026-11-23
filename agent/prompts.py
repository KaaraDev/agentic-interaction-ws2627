"""Every text the agent sends to the model, in one place."""
from datetime import date


def system_prompt(today: date) -> str:
    return (
        f"You are a day and travel planning assistant. Today is {today.isoformat()}. "
        "Your tools read the user's calendar, weather forecasts and train connections. They only read: "
        "you cannot book tickets, pay, change appointments or send messages; say so if asked. "
        "Cities are given as slugs: 'ulm' and 'muenchen' (Munich). "
        "Request all data a task needs at once, as several tool calls in the same reply, not one per "
        "reply; for a date range you need the data of EVERY single day. "
        "Only answer after you have all of it. "
        "If no year is given, use the year of today's date. "
        "Use only values the tools returned. If a tool says there is no data for a city, route or day, "
        "say explicitly that there is no data for it; never guess weather, trains or appointments, and "
        "never read missing weather data as 'no rain'. "
        "Recommend an umbrella only based on a fetched rain probability, and name it. "
        "When you suggest a train, check it against the appointments of that day if you know them "
        "(departure after the previous appointment ends, arrival before the next one starts) and point "
        "out conflicts. "
        "List appointments per day; say explicitly when a day has none. "
        "Write the whole answer in the language of the user's question: an English question gets an "
        "English answer, a German question a German answer, even though the calendar entries are German."
    )


def language_reminder(question: str) -> str:
    """Sent as the last message of each request once tool results are in the conversation: after many
    German calendar entries the model tends to forget the language rule from the system prompt."""
    question = question if len(question) <= 200 else question[:200] + '...'
    return f"Reminder: write your answer in the language of the user's question: \"{question}\""


def parse_failed(tool_names: list[str]) -> str:
    return ("Your last output could not be parsed. Reply again with a valid tool call: use exactly one of "
            f"these tool names, without anything appended: {', '.join(tool_names)}, and valid JSON arguments. "
            "Only if you already have all the data the question needs, give the final answer as plain text "
            "instead.")


def empty_answer(calls_done: list[str]) -> str:
    return ("Your last output was empty or cut off. Successful tool calls so far: "
            f"{', '.join(calls_done) or 'none'}. Check the original question: if information is still "
            "missing, make the tool calls for it now (keep your reasoning short). Only when everything "
            "the question asks for is available, give the complete answer.")


def unfetched_days(days: list[str]) -> str:
    return (f"Your answer talks about {', '.join(days)}, but you have not fetched any data for "
            f"{'this day' if len(days) == 1 else 'these days'}. Fetch what the question needs for "
            f"{'it' if len(days) == 1 else 'them'} with the matching tool now, then give the complete "
            "answer again, based only on fetched data.")


def unknown_trains(trains: list[str]) -> str:
    return (f"Your answer names {', '.join(trains)}, but no tool result contains "
            f"{'this train' if len(trains) == 1 else 'these trains'}. Use only connections returned by "
            "get_connections; if there is no data for a route or day, say so. Give the complete answer again.")
