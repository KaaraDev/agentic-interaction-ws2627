import json
import os
import re
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

# Maximum number of successful model calls (= steps) per run, also across pauses.
MAX_STEPS = int(os.getenv('MAX_STEPS', '30'))
# Rate-limit waits up to this many seconds are simply waited out. Longer ones pause the run
# and ask the user whether to continue (partial results are shown first).
MAX_AUTO_WAIT_S = float(os.getenv('MAX_AUTO_WAIT_S', '10'))
MAX_TOOL_RESULT_CHARS = 4000
# Groq counts the reserved output tokens of every request against the tokens-per-minute limit, so
# a smaller reservation and less reasoning mean more requests per minute.
MAX_COMPLETION_TOKENS = int(os.getenv('MAX_COMPLETION_TOKENS', '1536'))
# reasoning_effort is understood by gpt-oss models; other models may reject it, so it is only
# sent by default for those (override with REASONING_EFFORT=low|medium|high, or empty to disable).
REASONING_EFFORT = os.getenv('REASONING_EFFORT', 'low' if 'gpt-oss' in (MODEL or '') else '')
# 'auto': ask the user at the rate limit only when stdin is a terminal; 'always' / 'never' force it.
# Without a person at the keyboard (tests, CI, pipes) the agent waits and continues on its own.
ASK_ON_RATE_LIMIT = os.getenv('ASK_ON_RATE_LIMIT', 'auto').lower()
# Unattended runs wait at most this long per rate-limit pause (a daily limit would take hours).
MAX_UNATTENDED_WAIT_S = float(os.getenv('MAX_UNATTENDED_WAIT_S', '180'))
MAX_PAUSES = 10

EXIT_ERROR = 1
EXIT_PARTIAL = 2  # stopped at the rate limit, rest not processed


# ----------------------------------------------------------------------------- errors

class RateLimited(Exception):
    def __init__(self, wait_s: float, detail: str):
        super().__init__(detail)
        self.wait_s = wait_s


class ModelError(Exception):
    def __init__(self, message: str, transient: bool = False, parse_failed: bool = False):
        super().__init__(message)
        self.transient = transient
        self.parse_failed = parse_failed  # the model produced output the API could not parse (HTTP 400)


class ToolError(Exception):
    """A tool failed in a way the model should be told about (not a crash of the run)."""


class RunAborted(Exception):
    def __init__(self, message: str, exit_code: int = EXIT_ERROR):
        super().__init__(message)
        self.exit_code = exit_code


# ----------------------------------------------------------------------------- log

class RunLog:
    """Writes one JSONL file per run, one line per event."""

    def __init__(self):
        self.run_id = uuid.uuid4().hex[:8]
        LOG_DIR.mkdir(exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.path = LOG_DIR / f'{stamp}_{self.run_id}.jsonl'
        # Rate-limit waits and retries are not events of their own (the spec fixes the event names);
        # they are summarised in the args of the final / error event.
        self.notes = []

    def note(self, text):
        self.notes.append(text)

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


# ----------------------------------------------------------------------------- tools

def get_calendar_day(day: str) -> str:
    """Read the appointments of one day from the calendar data source."""
    try:
        day = date.fromisoformat(day).isoformat()
    except (TypeError, ValueError):
        raise ToolError(f"Invalid date {day!r}, expected YYYY-MM-DD.") from None
    url = f"{DATA_BASE_URL.rstrip('/')}/calendar/{day}.json"
    try:
        with urllib.request.urlopen(url, timeout=10) as response:
            text = response.read().decode('utf-8')
        try:  # minify: the pretty-printed file wastes about 40% of the tokens
            return json.dumps(json.loads(text), ensure_ascii=False, separators=(',', ':'))
        except json.JSONDecodeError:
            return text
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return json.dumps({"date": day, "events": [], "note": "No calendar data for this day."})
        raise ToolError(f"HTTP {e.code} while reading {url}") from None
    except Exception as e:
        raise ToolError(f"{type(e).__name__} while reading {url}: {e}") from None


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


def run_tool(name: str, raw_args: str):
    """Execute one tool call. Never raises: returns (args, result_text, ok)."""
    try:
        args = json.loads(raw_args or '{}')
        if not isinstance(args, dict):
            raise ToolError("Tool arguments must be a JSON object.")
    except json.JSONDecodeError as e:
        return {}, json.dumps({"error": f"Arguments are not valid JSON: {e}"}), False
    except ToolError as e:
        return {}, json.dumps({"error": str(e)}), False

    func = TOOL_FUNCTIONS.get(name)
    if func is None:
        return args, json.dumps({"error": f"Unknown tool {name}"}), False
    try:
        result = func(**args)
    except ToolError as e:
        return args, json.dumps({"error": str(e)}), False
    except TypeError as e:  # wrong / missing argument names
        return args, json.dumps({"error": f"Bad arguments for {name}: {e}"}), False
    except Exception as e:
        return args, json.dumps({"error": f"{type(e).__name__}: {e}"}), False
    if len(result) > MAX_TOOL_RESULT_CHARS:
        result = result[:MAX_TOOL_RESULT_CHARS] + '... [truncated]'
    return args, result, True


# ----------------------------------------------------------------------------- model

def parse_duration(text: str):
    """'7.5s', '1m6.5s', '250ms', '1h2m' -> seconds. None if nothing found."""
    parts = re.findall(r'([\d.]+)(ms|h|m|s)', text)
    if not parts:
        return None
    unit = {'ms': 0.001, 's': 1, 'm': 60, 'h': 3600}
    try:
        return sum(float(n) * unit[u] for n, u in parts)
    except ValueError:
        return None


def retry_wait_seconds(headers, body: str) -> float:
    """How long until the rate limit allows another call (Retry-After header, else Groq's message)."""
    value = headers.get('retry-after') if headers else None
    if value:
        try:
            return float(value)
        except ValueError:
            pass
    match = re.search(r'try again in\s+([\w.]+)', body)
    if match:
        seconds = parse_duration(match.group(1))
        if seconds is not None:
            return seconds
    return 30.0  # unknown: assume half a minute


def chat(messages):
    """One call to the OpenAI-compatible chat completions endpoint (plain HTTP)."""
    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "temperature": 0.3,  # lower than the default: fewer malformed tool calls
        "max_completion_tokens": MAX_COMPLETION_TOKENS,
    }
    if REASONING_EFFORT:
        payload["reasoning_effort"] = REASONING_EFFORT
    body = json.dumps(payload).encode('utf-8')
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
            choice = json.loads(response.read().decode('utf-8'))['choices'][0]
            return choice['message'], choice.get('finish_reason')
    except urllib.error.HTTPError as e:
        text = e.read().decode('utf-8', 'replace')
        if e.code == 429:
            raise RateLimited(retry_wait_seconds(e.headers, text), text) from None
        if e.code == 413:
            raise ModelError(f"Request too large for the model's token limit (HTTP 413): {text}") from None
        if e.code == 400 and 'output_parse_failed' in text:
            # Flaky generation (e.g. a malformed tool call): sampling again usually works.
            raise ModelError(f"Model output could not be parsed (HTTP 400): {text}",
                             transient=True, parse_failed=True) from None
        raise ModelError(f"HTTP {e.code} from model endpoint: {text}", transient=e.code >= 500) from None
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise ModelError(f"{type(e).__name__} talking to the model endpoint: {e}", transient=True) from None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        raise ModelError(f"Unexpected response from model endpoint: {e}", transient=True) from None


def call_model(messages, log):
    """chat() with retries for short rate-limit waits and transient errors.

    Raises RateLimited when the wait is too long to just sit out (caller pauses and asks the user)
    and ModelError when the model call keeps failing.
    """
    auto_waits = 0
    retries = 0
    while True:
        try:
            return chat(messages)
        except RateLimited as e:
            if e.wait_s <= MAX_AUTO_WAIT_S and auto_waits < 3:
                auto_waits += 1
                log.note(f'waited {e.wait_s:.1f}s for rate limit')
                time.sleep(e.wait_s + 0.5)
                continue
            raise
        except ModelError as e:
            if e.transient and retries < 3:
                retries += 1
                log.note(f'model retry {retries}: {e}')
                time.sleep(2 * retries)
                continue
            raise


# ----------------------------------------------------------------------------- agent loop

def partial_report(collected):
    if not collected:
        return "  (nothing collected yet)"
    lines = []
    for tool, args, result, ok in collected:
        preview = result.replace('\n', ' ')
        preview = preview if len(preview) <= 200 else preview[:200] + '...'
        lines.append(f"  - {tool}({json.dumps(args, ensure_ascii=False)}): {'' if ok else 'FAILED: '}{preview}")
    return '\n'.join(lines)


def wants_to_ask() -> bool:
    if ASK_ON_RATE_LIMIT == 'always':
        return True
    if ASK_ON_RATE_LIMIT == 'never':
        return False
    # Both must be a terminal: on Windows the null device (stdin=DEVNULL) reports isatty() == True,
    # and a test harness always captures stdout.
    return bool(sys.stdin and sys.stdin.isatty() and sys.stdout and sys.stdout.isatty())


def ask_continue(collected, wait_s) -> bool:
    """Show what is done so far and ask whether to go on. No answer (EOF) counts as 'no'."""
    wait_txt = f"{wait_s:.0f} s" if wait_s < 120 else f"{wait_s / 60:.1f} min"
    print("\nThe model's token limit (rate limit) is reached. Request only partly processed.\n"
          "Results gathered so far:\n" + partial_report(collected) + "\n\n"
          f"The limit resets in about {wait_txt}. Process the rest of the request now? [y/N] ",
          end='', file=sys.stderr, flush=True)
    answer = sys.stdin.readline().strip().lower()
    return answer in ('y', 'yes', 'j', 'ja')


def countdown(wait_s):
    end = time.monotonic() + wait_s + 1
    while (left := end - time.monotonic()) > 0:
        print(f"\rWaiting for the limit to reset: {left:4.0f} s ", end='', file=sys.stderr, flush=True)
        time.sleep(min(1, left))
    print(file=sys.stderr)


def run(prompt, log):
    messages = [
        {
            "role": "system",
            "content": f"You are a helpful calendar assistant. Today is {date.today().isoformat()}. "
                       "Use the calendar tool to answer questions about appointments. Answer in the user's language. "
                       "For a date range or several days, call the tool for EVERY single day of the range "
                       "(you may request several days in one step) and only answer after you have the data of all "
                       "of them. If no year is given, use the year of today's date. "
                       "Never claim that a day has no appointments unless the tool returned that for this day. "
                       "Then list the appointments per day; say explicitly when a day has none."
        },
        {"role": "user", "content": prompt}
    ]
    pauses = 0
    nudges = 0
    collected = []  # (tool, args, result, ok) of every tool call so far
    steps = 0

    while steps < MAX_STEPS:
        started = time.perf_counter()
        try:
            message, finish_reason = call_model(messages, log)
        except RateLimited as e:
            pauses += 1
            if wants_to_ask():
                if not ask_continue(collected, e.wait_s):
                    raise RunAborted("Stopped at the token limit; the request is only partly processed.\n"
                                     "Results so far:\n" + partial_report(collected), EXIT_PARTIAL) from None
            elif e.wait_s > MAX_UNATTENDED_WAIT_S or pauses > MAX_PAUSES:
                raise RunAborted(f"Token limit reached (resets in about {e.wait_s:.0f} s) and nobody is there to "
                                 "confirm waiting. Request only partly processed.\n"
                                 "Results so far:\n" + partial_report(collected), EXIT_PARTIAL) from None
            log.note(f'rate limit pause {pauses}: {len(collected)} tool calls done, waited {e.wait_s:.0f}s')
            countdown(e.wait_s)
            continue
        except ModelError as e:
            if e.parse_failed and nudges < 3:
                # Retries did not help: tell the model what went wrong and let it try differently.
                # This counts as a step, so the run still ends at MAX_STEPS.
                nudges += 1
                steps += 1
                log.note(f'parse failure, nudged the model ({nudges})')
                messages.append({"role": "user", "content": (
                    "Your last output could not be parsed. Reply again: call get_calendar_day for ONE "
                    "day with valid JSON arguments, or give the final answer as plain text.")})
                continue
            raise RunAborted(f"Model call failed: {e}") from None

        steps += 1
        duration_ms = round((time.perf_counter() - started) * 1000)

        tool_calls = message.get('tool_calls')
        if not tool_calls:
            content = (message.get('content') or '').strip()
            if not content or finish_reason == 'length':
                # Empty or cut off (token cap): not a result. Do NOT push the model to answer now,
                # it would invent the data it has not fetched yet. Tell it what it has and let it go on.
                if nudges >= 3:
                    raise RunAborted("The model returned an empty or truncated answer.")
                nudges += 1  # this model call already counted as a step above
                queried =sorted({a.get('day') for _, a, _, ok in collected if ok and isinstance(a, dict)} - {None})
                log.note(f'empty/truncated answer (finish_reason={finish_reason}), nudged the model ({nudges})')
                messages.append({"role": "user", "content": (
                    "Your last output was empty or cut off. Days fetched so far: "
                    f"{', '.join(queried) or 'none'}. Check the original question: if days are still missing, "
                    "call get_calendar_day for them now (keep your reasoning short). Only when the data of "
                    "all requested days is available, give the complete answer.")})
                continue
            # The 'final' event is written by main() once the answer has actually been printed,
            # so a run always ends with exactly one 'final' or one 'error' event.
            return content, duration_ms

        # Keep only what the API needs; extra fields (e.g. reasoning) would eat into the token budget.
        messages.append({"role": "assistant", "content": message.get('content'), "tool_calls": tool_calls})
        for call in tool_calls:
            name = call['function']['name']
            raw_args = call['function'].get('arguments')
            try:
                logged_args = json.loads(raw_args or '{}')
            except json.JSONDecodeError:
                logged_args = raw_args
            log.write('tool_call', tool=name, args=logged_args, ok=True, duration_ms=duration_ms)

            started = time.perf_counter()
            args, result, ok = run_tool(name, raw_args)
            log.write('tool_result', tool=name, args=args, ok=ok,
                      duration_ms=round((time.perf_counter() - started) * 1000))

            collected.append((name, args, result, ok))
            messages.append({"role": "tool", "tool_call_id": call['id'], "content": result})

    raise RunAborted(f"No final answer after {MAX_STEPS} steps")


def main():
    if len(sys.argv) < 2:
        sys.exit('Usage: python -m agent "<your question>"')
    # Redirected output on Windows defaults to cp1252, which cannot print every character a model
    # produces (e.g. U+202F). Never let printing the answer crash a finished run.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')
    prompt = " ".join(sys.argv[1:])
    if not prompt.strip():
        sys.exit('Usage: python -m agent "<your question>"')

    log = RunLog()
    log.write('user_task', args={'task': prompt}, ok=True)
    try:
        missing = [n for n, v in [('OPENAI_BASE_URL', OPENAI_BASE_URL), ('MODEL', MODEL),
                                  ('OPENAI_API_KEY', OPENAI_API_KEY), ('DATA_BASE_URL', DATA_BASE_URL)] if not v]
        if missing:
            raise RunAborted(f"Missing environment variables: {', '.join(missing)}")
        answer, duration_ms = run(prompt, log)
        print(answer, flush=True)
        log.write('final', ok=True, duration_ms=duration_ms, **({'args': {'notes': log.notes}} if log.notes else {}))
    except RunAborted as e:
        log.write('error', ok=False, args={'message': str(e), 'exit_code': e.exit_code, 'notes': log.notes})
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(e.exit_code)
    except BaseException as e:  # incl. Ctrl+C: the log must always record how the run ended
        log.write('error', ok=False, args={'message': f"{type(e).__name__}: {e}", 'notes': log.notes})
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(EXIT_ERROR)


if __name__ == '__main__':
    main()
