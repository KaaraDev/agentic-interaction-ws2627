"""The agent loop: call the model, run the tools it asks for, repeat until it gives an answer.

Every model call is one step; at most `config.max_steps` steps per run. Problems along the way
(tool errors, garbled model output, empty or invented answers, rate limits) are handled inside the
loop so a single bad step does not end the run. RunAborted ends it.
"""
import json
import time
from dataclasses import dataclass, field
from datetime import date

from . import prompts
from .config import Config
from .errors import EXIT_PARTIAL, ModelError, RateLimited, RunAborted
from .guards import unfetched_days
from .llm import Completion
from .log import RunLog
from .policies import PausePolicy, countdown, partial_report
from .tools import ToolRegistry, ToolResult
from .tools.calendar import NAME as CALENDAR_TOOL

MAX_NUDGES = 3        # corrections for garbled, empty or cut-off model output
MAX_GUARD_ROUNDS = 2  # corrections for answers about days that were not fetched


@dataclass
class RunState:
    messages: list[dict]
    results: list[ToolResult] = field(default_factory=list)
    steps: int = 0
    nudges: int = 0
    guard_rounds: int = 0
    pauses: int = 0


class Agent:
    def __init__(self, config: Config, client, tools: ToolRegistry, pause_policy: PausePolicy, log: RunLog):
        self.config = config
        self.client = client          # anything with complete(messages) -> Completion
        self.tools = tools
        self.pause_policy = pause_policy
        self.log = log

    def run(self, task: str) -> tuple[str, int]:
        """Returns (answer, duration of the last model call in ms). Raises RunAborted."""
        state = RunState(messages=[
            {"role": "system", "content": prompts.system_prompt(date.today())},
            {"role": "user", "content": task},
        ])
        while state.steps < self.config.max_steps:
            started = time.perf_counter()
            try:
                completion = self.client.complete(state.messages)
            except RateLimited as e:
                self._pause(state, e)
                continue
            except ModelError as e:
                self._recover_from_model_error(state, e)
                continue
            state.steps += 1
            duration_ms = round((time.perf_counter() - started) * 1000)

            if completion.tool_calls:
                self._run_tools(state, completion, duration_ms)
                continue
            answer = self._accept_answer(state, completion)
            if answer is not None:
                return answer, duration_ms
        raise RunAborted(f"No final answer after {self.config.max_steps} steps")

    # ------------------------------------------------------------------ steps

    def _run_tools(self, state: RunState, completion: Completion, duration_ms: int) -> None:
        # Send back only what the API needs; extra fields (e.g. reasoning) would cost tokens.
        state.messages.append({"role": "assistant", "content": completion.message.get('content'),
                               "tool_calls": completion.tool_calls})
        for call in completion.tool_calls:
            function = call.get('function') or {}
            name = function.get('name') or '<missing>'
            raw_args = function.get('arguments')
            self.log.write('tool_call', tool=name, args=_args_for_log(raw_args), ok=True, duration_ms=duration_ms)

            started = time.perf_counter()
            result = self.tools.execute(name, raw_args)
            self.log.write('tool_result', tool=name, args=result.args, ok=result.ok,
                           duration_ms=round((time.perf_counter() - started) * 1000))

            state.results.append(result)
            state.messages.append({"role": "tool", "tool_call_id": call.get('id', ''), "content": result.content})

    def _accept_answer(self, state: RunState, completion: Completion) -> str | None:
        """The answer if it can be accepted; otherwise the model is corrected and None returned."""
        content = completion.content
        if not content or completion.finish_reason == 'length':
            # Empty or cut off by the token cap. Do not push the model to answer now: it would invent
            # the data it has not fetched yet. Tell it what it has and let it go on.
            if state.nudges >= MAX_NUDGES:
                raise RunAborted("The model returned an empty or truncated answer.")
            state.nudges += 1
            self.log.note(f'empty/truncated answer (finish_reason={completion.finish_reason}), '
                          f'nudged the model ({state.nudges})')
            calls_done = [f"{r.tool}({json.dumps(r.args, ensure_ascii=False)})" for r in state.results if r.ok]
            state.messages.append({"role": "user", "content": prompts.empty_answer(calls_done)})
            return None

        missing = unfetched_days(content, state.results)
        if missing and state.guard_rounds < MAX_GUARD_ROUNDS:
            state.guard_rounds += 1
            self.log.note(f'answer mentions unfetched days {missing}, '
                          f'asked the model to fetch them ({state.guard_rounds})')
            state.messages.append({"role": "assistant", "content": content})
            state.messages.append({"role": "user", "content": prompts.unfetched_days(missing, CALENDAR_TOOL)})
            return None
        return content

    # ------------------------------------------------------------------ problems

    def _pause(self, state: RunState, e: RateLimited) -> None:
        state.pauses += 1
        if not self.pause_policy.should_continue(e.wait_s, state.pauses, state.results):
            raise RunAborted(f"{self.pause_policy.stop_message(e.wait_s)}\n"
                             f"Endpoint: {e}\n"
                             f"Results so far:\n{partial_report(state.results)}", EXIT_PARTIAL) from None
        self.log.note(f'rate limit pause {state.pauses}: {len(state.results)} tool calls done, '
                      f'waited {e.wait_s:.0f}s ({e})')
        countdown(e.wait_s)

    def _recover_from_model_error(self, state: RunState, e: ModelError) -> None:
        """Retries already failed. For garbled output, tell the model and let it try differently
        (this counts as a step, so the step limit still applies); everything else ends the run."""
        if not e.parse_failed or state.nudges >= MAX_NUDGES:
            raise RunAborted(f"Model call failed: {e}") from None
        state.nudges += 1
        state.steps += 1
        self.log.note(f'parse failure, nudged the model ({state.nudges})')
        state.messages.append({"role": "user", "content": prompts.parse_failed(self.tools.names())})


def _args_for_log(raw_args):
    try:
        return json.loads(raw_args or '{}')
    except json.JSONDecodeError:
        return raw_args
