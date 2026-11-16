"""Every text the agent sends to the model, in one place."""
from datetime import date


def system_prompt(today: date) -> str:
    return (
        f"You are a helpful calendar assistant. Today is {today.isoformat()}. "
        "Use the calendar tool to answer questions about appointments. "
        "For a date range or several days, call the tool for EVERY single day of the range "
        "(you may request several days in one step) and only answer after you have the data of all of them. "
        "If no year is given, use the year of today's date. "
        "Never claim that a day has no appointments unless the tool returned that for this day. "
        "List the appointments per day; say explicitly when a day has none. "
        "Write the whole answer in the language of the user's question: an English question gets an "
        "English answer, a German question a German answer, even though the calendar entries are German."
    )


def parse_failed(tool_names: list[str]) -> str:
    return ("Your last output could not be parsed. Reply again: make ONE tool call with valid JSON "
            f"arguments (available tools: {', '.join(tool_names)}), or give the final answer as plain text.")


def empty_answer(calls_done: list[str]) -> str:
    return ("Your last output was empty or cut off. Successful tool calls so far: "
            f"{', '.join(calls_done) or 'none'}. Check the original question: if information is still "
            "missing, make the tool calls for it now (keep your reasoning short). Only when everything "
            "the question asks for is available, give the complete answer.")


def unfetched_days(days: list[str], tool_name: str) -> str:
    return (f"Your answer talks about {', '.join(days)}, but you have not fetched "
            f"{'this day' if len(days) == 1 else 'these days'} with {tool_name}. "
            "Fetch them now, then give the complete answer again, based only on fetched data.")
