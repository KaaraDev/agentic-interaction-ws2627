"""Entry point: python -m agent "<question>"

Prints the answer to stdout (exit code 0). Errors go to stderr with exit code 1, a request stopped
at the token limit exits with 2. Every run writes a log that ends with one 'final' or 'error' event.
"""
import os
import sys
from pathlib import Path

if not __package__:  # started as a file (python agent/__main__.py), e.g. by an IDE run configuration:
    # import from the repository root instead of from inside agent/
    sys.path[0] = str(Path(__file__).resolve().parent.parent)

from agent.agent import Agent  # noqa: E402
from agent.config import Config  # noqa: E402  (importing it reads .env)
from agent.errors import EXIT_ERROR, EXIT_OK, RunAborted  # noqa: E402
from agent.llm import ChatClient, RetryingClient  # noqa: E402
from agent.log import RunLog  # noqa: E402
from agent.policies import choose_policy  # noqa: E402
from agent.tools import build_registry  # noqa: E402

USAGE = 'Usage: python -m agent "<your question>"'


def build_agent(config: Config, log: RunLog) -> Agent:
    tools = build_registry(config)
    client = RetryingClient(ChatClient(config, tools.schemas()), log, config.max_auto_wait_s)
    return Agent(config, client, tools, choose_policy(config), log)


def main(argv: list[str]) -> int:
    # Redirected output on Windows defaults to cp1252, which cannot print every character a model
    # produces (e.g. U+202F). Printing the answer must never crash a finished run.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8', errors='replace')

    task = ' '.join(argv)
    log = RunLog(model=os.getenv('MODEL'))  # created first: even a misconfigured run leaves a log
    log.write('user_task', args={'task': task}, ok=True)
    try:
        if not task.strip():
            raise RunAborted(USAGE)
        config = Config.from_env()
        answer, duration_ms = build_agent(config, log).run(task)
        print(answer, flush=True)
        # Written only after the answer is out, so a run ends with exactly one 'final' or 'error'.
        log.write('final', ok=True, duration_ms=duration_ms, **({'args': {'notes': log.notes}} if log.notes else {}))
        return EXIT_OK
    except RunAborted as e:
        log.write('error', ok=False, args={'message': str(e), 'exit_code': e.exit_code, 'notes': log.notes})
        print(f"Error: {e}", file=sys.stderr)
        return e.exit_code
    except BaseException as e:  # including Ctrl+C: the log must always record how the run ended
        log.write('error', ok=False, args={'message': f"{type(e).__name__}: {e}", 'notes': log.notes})
        print(f"Error: {type(e).__name__}: {e}", file=sys.stderr)
        return EXIT_ERROR


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
