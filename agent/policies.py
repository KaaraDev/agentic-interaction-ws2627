"""What to do when the token limit is reached and the wait is too long to just sit out (strategy).

WaitAlone   default: wait for the reset and go on, within a total wait budget per run
AskUser     only when configured (ASK_ON_RATE_LIMIT): show the partial results and ask whether to go on
"""
import json
import sys
import time

from .config import Config


class PausePolicy:
    def should_continue(self, wait_s: float, pauses: int, results) -> bool:
        raise NotImplementedError

    def stop_message(self, wait_s: float) -> str:
        raise NotImplementedError


class AskUser(PausePolicy):
    def should_continue(self, wait_s, pauses, results):
        wait = f"{wait_s:.0f} s" if wait_s < 120 else f"{wait_s / 60:.1f} min"
        print("\nThe model's token limit (rate limit) is reached. Request only partly processed.\n"
              "Results gathered so far:\n" + partial_report(results) + "\n\n"
              f"The limit resets in about {wait}. Process the rest of the request now? [y/N] ",
              end='', file=sys.stderr, flush=True)
        return sys.stdin.readline().strip().lower() in ('y', 'yes', 'j', 'ja')  # EOF counts as no

    def stop_message(self, wait_s):
        return "Stopped at the token limit; the request is only partly processed."


class WaitAlone(PausePolicy):
    """Waits without asking, as long as all pauses of the run together stay within the budget.
    (A per-minute limit resets within a minute; a daily limit can ask for minutes or hours.)"""

    def __init__(self, wait_budget_s: float, max_pauses: int):
        self.wait_budget_s = wait_budget_s
        self.max_pauses = max_pauses
        self.waited_s = 0.0

    def should_continue(self, wait_s, pauses, results):
        if pauses > self.max_pauses or self.waited_s + wait_s > self.wait_budget_s:
            return False
        self.waited_s += wait_s
        return True

    def stop_message(self, wait_s):
        return (f"Token limit reached (resets in about {wait_s:.0f} s). Nobody is there to confirm waiting "
                f"and the wait budget of this run ({self.wait_budget_s:.0f} s, {self.waited_s:.0f} s used) "
                "does not cover it. Request only partly processed.")


def choose_policy(config: Config) -> PausePolicy:
    mode = config.ask_on_rate_limit
    if mode == 'always':
        return AskUser()
    if mode == 'auto':
        # Both must be a terminal: on Windows the null device (stdin=DEVNULL) reports isatty() == True.
        if sys.stdin and sys.stdin.isatty() and sys.stdout and sys.stdout.isatty():
            return AskUser()
    return WaitAlone(config.max_unattended_wait_s, config.max_pauses)  # 'never' (default)


def partial_report(results) -> str:
    if not results:
        return "  (nothing collected yet)"
    lines = []
    for r in results:
        preview = r.content.replace('\n', ' ')
        preview = preview if len(preview) <= 200 else preview[:200] + '...'
        lines.append(f"  - {r.tool}({json.dumps(r.args, ensure_ascii=False)}): {'' if r.ok else 'FAILED: '}{preview}")
    return '\n'.join(lines)


def countdown(wait_s: float) -> None:
    end = time.monotonic() + wait_s + 1
    while (left := end - time.monotonic()) > 0:
        print(f"\rWaiting for the limit to reset: {left:4.0f} s ", end='', file=sys.stderr, flush=True)
        time.sleep(min(1, left))
    print(file=sys.stderr)
