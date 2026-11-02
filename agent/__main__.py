import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

# Environment variables take precedence over .env (override=False is the default).
load_dotenv()

OPENAI_BASE_URL = os.getenv('OPENAI_BASE_URL')
MODEL = os.getenv('MODEL')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
DATA_BASE_URL = os.getenv('DATA_BASE_URL')

LOG_DIR = Path(__file__).resolve().parent.parent / 'logs'
MAX_STEPS = 5


class RunLog:
    """Writes one JSONL file per run, one line per event."""

    def __init__(self):
        self.run_id = uuid.uuid4().hex[:8]
        LOG_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.path = LOG_DIR / f'{stamp}_{self.run_id}.jsonl'

    def write(self, event, **fields):
        entry = {
            'ts': datetime.now(timezone.utc).isoformat(),
            'run_id': self.run_id,
            'event': event,
            'model': MODEL,
            **fields,
        }
        with open(self.path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def get_calendar_day(day: str) -> str:
    """Read the appointments of one day from the calendar data source."""
    url = f"{DATA_BASE_URL}/calendar/{day}.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return json.dumps({"date": day, "events": [], "note": "No calendar data for this day."})
        return json.dumps({"error": f"HTTP {e.code} while reading {url}"})
    except Exception as e:
        return json.dumps({"error": str(e)})


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_calendar_day",
            "description": (
                "Returns the calendar appointments of the user for exactly one day "
                "(title, start and end time, location, all-day flag). "
                "Call it once per day the user asks about."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "day": {
                        "type": "string",
                        "description": "The day to look up in ISO format YYYY-MM-DD, e.g. 2026-10-29."
                    }
                },
                "required": ["day"]
            }
        }
    }
]

TOOL_FUNCTIONS = {"get_calendar_day": get_calendar_day}


def chat(messages):
    """One call to the OpenAI-compatible chat completions endpoint (plain HTTP)."""
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 1,
        "max_completion_tokens": 2048,
    }).encode('utf-8')
    request = urllib.request.Request(
        f"{OPENAI_BASE_URL.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "User-Agent": "agentic-interaction-agent/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode('utf-8'))['choices'][0]['message']
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} from model endpoint: {e.read().decode('utf-8', 'replace')}") from None


def run(prompt, log):
    messages = [
        {
            "role": "system",
            "content": f"You are a helpful calendar assistant. Today is {date.today().isoformat()}. "
                       "Use the calendar tool to answer questions about appointments. Answer in the user's language."
        },
        {"role": "user", "content": prompt}
    ]

    for _ in range(MAX_STEPS):
        started = time.perf_counter()
        message = chat(messages)
        duration_ms = round((time.perf_counter() - started) * 1000)

        tool_calls = message.get('tool_calls')
        if not tool_calls:
            log.write('final', ok=True, duration_ms=duration_ms)
            return message.get('content') or ''

        messages.append(message)
        for call in tool_calls:
            name = call['function']['name']
            args = json.loads(call['function'].get('arguments') or '{}')
            log.write('tool_call', tool=name, args=args, ok=True, duration_ms=duration_ms)

            started = time.perf_counter()
            if name in TOOL_FUNCTIONS:
                result = TOOL_FUNCTIONS[name](**args)
                ok = '"error"' not in result
            else:
                result = json.dumps({"error": f"Unknown tool {name}"})
                ok = False
            log.write('tool_result', tool=name, args=args, ok=ok,
                      duration_ms=round((time.perf_counter() - started) * 1000))

            messages.append({"role": "tool", "tool_call_id": call['id'], "content": result})

    raise RuntimeError(f"No final answer after {MAX_STEPS} steps")


def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: python -m agent "<your question>"')
    prompt = " ".join(sys.argv[1:])

    missing = [n for n, v in [('OPENAI_BASE_URL', OPENAI_BASE_URL), ('MODEL', MODEL),
                              ('OPENAI_API_KEY', OPENAI_API_KEY), ('DATA_BASE_URL', DATA_BASE_URL)] if not v]
    if missing:
        sys.exit(f"Missing environment variables: {', '.join(missing)}")

    log = RunLog()
    log.write('user_task', args={'task': prompt}, ok=True)
    try:
        print(run(prompt, log))
    except Exception as e:
        log.write('error', ok=False, args={'message': str(e)})
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
