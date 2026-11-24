"""Every text the agent sends to the model, in one place."""
from datetime import date

from .guards import language_of


def system_prompt(today: date) -> str:
    return (
        f"You are a day and travel planning assistant. Today is {today.isoformat()}. "
        "Your tools read the user's calendar, weather forecasts and train connections. They only read: "
        "you cannot book tickets, pay, change appointments or send messages; say so if asked. "
        "Cities are given as slugs: 'ulm' and 'muenchen' (Munich). "
        "Fetch only what the question asks for: no weather for a pure calendar question, no trains for "
        "a pure weather question. For weather on a trip, use the city the question means (\"there\" "
        "is the destination). "
        "Request all of it at once, as several tool calls in the same reply, not one per reply; for a "
        "date range you need the data of EVERY single day. "
        "Only answer after you have all of it. "
        "If no year is given, use the year of today's date. "
        "Use only values the tools returned. If a tool says there is no data for a city, route or day, "
        "say explicitly that there is no data for it; never guess weather, trains or appointments, and "
        "never read missing weather data as 'no rain'. "
        "Recommend an umbrella only based on a fetched rain probability, and name it: from 50 % on take "
        "one, from 30 % it may be useful, below 30 % it is not needed. "
        "To get to an appointment, the train goes from where the user is before it (home is Ulm) to the "
        "appointment's city, e.g. to the workshop visit in Munich: origin ulm, destination muenchen. "
        "Add nothing the tools did not return: no product or brand names, no other transport, no "
        "general travel tips. "
        "get_connections already checks every connection against the calendar of that day: do not "
        "compare times yourself, use its 'check'. For every connection you mention, say whether it fits "
        "and name its conflicts and warnings. Recommend only connections that fit; if none fits, say "
        "clearly that no connection fits and why. "
        "Never say anything about appointments of a day whose calendar you have not fetched. "
        "List appointments per day; say explicitly when a day has none. "
        "Write the whole answer in the language of the user's question: an English question gets an "
        "English answer, a German question a German answer, even though the calendar entries are German."
    )


def language_reminder(question: str) -> str:
    """Sent as the last message of each request once tool results are in the conversation: after many
    German calendar entries the model tends to forget the language rule from the system prompt.
    Naming the language explicitly works better than asking the model to work it out."""
    language = language_of(question)
    if language:
        return (f"Reminder: the user's question is in {language}. Write the whole answer in {language}, "
                f"including table headings; translate German data values where needed.")
    question = question if len(question) <= 200 else question[:200] + '...'
    return f"Reminder: write your answer in the language of the user's question: \"{question}\""


def wrong_language(language: str) -> str:
    return (f"Your answer is not in {language}, the language of the user's question. "
            f"Give the complete answer again, entirely in {language}.")


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


def unreported_conflicts(conflicts: dict[str, str]) -> str:
    listed = '; '.join(f"{train}: {reason}" for train, reason in sorted(conflicts.items()))
    return ("According to the calendar check in the get_connections result, these connections do NOT fit: "
            f"{listed}. Your answer mentions them without saying so. Give the complete answer again and "
            "state the conflict for every connection that does not fit.")


def unknown_trains(trains: list[str]) -> str:
    return (f"Your answer names {', '.join(trains)}, but no tool result contains "
            f"{'this train' if len(trains) == 1 else 'these trains'}. Use only connections returned by "
            "get_connections; if there is no data for a route or day, say so. Give the complete answer again.")
