"""Model access over plain HTTP (OpenAI-compatible chat completions, works with any such endpoint).

ChatClient      one request, HTTP errors translated into RateLimited / ModelError
RetryingClient  wraps a client (decorator): sits out short rate-limit waits, retries transient errors
"""
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from .config import Config
from .errors import ModelError, RateLimited
from .log import RunLog


@dataclass(frozen=True)
class Completion:
    message: dict
    finish_reason: str | None

    @property
    def tool_calls(self) -> list:
        return self.message.get('tool_calls') or []

    @property
    def content(self) -> str:
        return (self.message.get('content') or '').strip()


class ChatClient:
    def __init__(self, config: Config, tool_schemas: list[dict]):
        self.config = config
        self.tool_schemas = tool_schemas
        # Optional request parameters. Not every OpenAI-compatible endpoint knows all of them; one
        # that the endpoint rejects (HTTP 400 naming it) is replaced or left out for the rest of the run.
        self._optional = {"max_completion_tokens": config.max_completion_tokens}
        if config.reasoning_effort:
            self._optional["reasoning_effort"] = config.reasoning_effort

    def complete(self, messages: list[dict]) -> Completion:
        while True:
            try:
                return self._request(messages)
            except _RejectedParameter:
                continue  # self._optional was adapted, send again

    def _adapt_to_rejection(self, error_text: str) -> bool:
        """True if the error names one of our optional parameters and it was replaced / removed."""
        for name in list(self._optional):
            if name in error_text:
                value = self._optional.pop(name)
                if name == "max_completion_tokens":  # older name of the same setting
                    self._optional["max_tokens"] = value
                return True
        return False

    def _request(self, messages: list[dict]) -> Completion:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "tools": self.tool_schemas,
            "tool_choice": "auto",
            "temperature": self.config.temperature,
            **self._optional,
        }
        request = urllib.request.Request(
            f"{self.config.base_url}/chat/completions",
            data=json.dumps(payload).encode('utf-8'),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
                "User-Agent": "agentic-interaction-agent/1.0",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                choice = json.loads(response.read().decode('utf-8'))['choices'][0]
                return Completion(choice['message'], choice.get('finish_reason'))
        except urllib.error.HTTPError as e:
            text = e.read().decode('utf-8', 'replace')
            if e.code == 400 and not _is_generation_failure(text) and self._adapt_to_rejection(text):
                raise _RejectedParameter() from None
            raise _translate_http_error(e.code, e.headers, text) from None
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            raise ModelError(f"{type(e).__name__} talking to the model endpoint: {e}", transient=True) from None
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            raise ModelError(f"Unexpected response from model endpoint: {e}", transient=True) from None


class _RejectedParameter(Exception):
    """Internal: the endpoint refused an optional parameter; the request is sent again without it."""


def _translate_http_error(code: int, headers, text: str) -> Exception:
    if code == 429:
        return RateLimited(retry_wait_seconds(headers, text), _error_message(text))
    if code == 413:  # a single request above the limit: waiting does not help
        return ModelError(f"Request too large for the model's token limit (HTTP 413): {text}")
    if code == 400 and _is_generation_failure(text):  # garbled generation: sampling again usually works
        return ModelError(f"Model output could not be parsed (HTTP 400): {text}", transient=True, parse_failed=True)
    return ModelError(f"HTTP {code} from model endpoint: {text}", transient=code >= 500)


def _error_message(body: str) -> str:
    """The endpoint's own explanation (e.g. which limit was hit: per minute or per day)."""
    try:
        return str(json.loads(body)['error']['message'])
    except (json.JSONDecodeError, KeyError, TypeError):
        return body.strip()[:300]


def _is_generation_failure(body: str) -> bool:
    """HTTP 400 caused by what the model generated, not by our request.

    Recognised by the endpoint handing back the failed generation, by Groq's error codes
    ('output_parse_failed', 'tool_use_failed', e.g. a tool name like 'get_calendar_day<|channel|>commentary')
    or by the usual wording of such errors on other endpoints.
    """
    if 'failed_generation' in body or 'output_parse_failed' in body or 'tool_use_failed' in body:
        return True
    return bool(re.search(r'fail\w* to parse|could not be parsed|parsing failed|tool call validation|'
                          r'(invalid|malformed) (tool|function)[ _]call', body, re.I))


def retry_wait_seconds(headers, body: str) -> float:
    """Seconds until the rate limit allows another call: Retry-After header, else Groq's message."""
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


def parse_duration(text: str) -> float | None:
    """'7.5s', '1m6.5s', '250ms', '1h2m' -> seconds; None if there is no duration in the text."""
    units = {'ms': 0.001, 's': 1, 'm': 60, 'h': 3600}
    parts = re.findall(r'([\d.]+)(ms|h|m|s)', text)
    try:
        return sum(float(number) * units[unit] for number, unit in parts) if parts else None
    except ValueError:
        return None


class RetryingClient:
    """Same interface as ChatClient. Raises RateLimited only for waits too long to just sit out
    (the agent then pauses) and ModelError only once retrying has not helped."""

    MAX_AUTO_WAITS = 3
    MAX_RETRIES = 3

    def __init__(self, client: ChatClient, log: RunLog, max_auto_wait_s: float, sleep=time.sleep):
        self.client = client
        self.log = log
        self.max_auto_wait_s = max_auto_wait_s
        self.sleep = sleep

    def complete(self, messages: list[dict]) -> Completion:
        auto_waits = retries = 0
        while True:
            try:
                return self.client.complete(messages)
            except RateLimited as e:
                if e.wait_s > self.max_auto_wait_s or auto_waits >= self.MAX_AUTO_WAITS:
                    raise
                auto_waits += 1
                self.log.note(f'waited {e.wait_s:.1f}s for rate limit')
                self.sleep(e.wait_s + 0.5)
            except ModelError as e:
                if not e.transient or retries >= self.MAX_RETRIES:
                    raise
                retries += 1
                self.log.note(f'model retry {retries}: {e}')
                self.sleep(2 * retries)
