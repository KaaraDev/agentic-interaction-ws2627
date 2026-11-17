# agentic-interaction-ws2627

Calendar agent: the model calls the tool `get_calendar_day`, which reads the appointments of one
day from `{DATA_BASE_URL}/calendar/{YYYY-MM-DD}.json`, as many times as the task needs, and then
answers.

## Setup

Python 3.11 or newer.

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Create a `.env` file (never commit it). Environment variables take precedence over `.env`.

```
OPENAI_BASE_URL=https://api.groq.com/openai/v1
MODEL=openai/gpt-oss-20b
OPENAI_API_KEY=<your Groq key>
DATA_BASE_URL=https://jhbelz.github.io/agentic-interaction-data/v1
```

## Run

From the repository root:

```bash
python -m agent "What is on 29 Oct 2026 and on 30 Oct 2026?"
```

The answer is printed to standard output (exit code 0).

## Code structure

```
agent/
  __main__.py     entry point: runs the agent, prints the answer, logs how the run ended, exit code
  config.py       settings from the environment / .env (Config)
  agent.py        the agent loop (Agent): model call -> tools -> ... -> answer
  llm.py          HTTP client for the OpenAI-compatible endpoint (ChatClient) and retries (RetryingClient)
  tools/
    base.py       Tool, ToolRegistry: tools describe themselves to the model and are run by name
    calendar.py   get_calendar_day
    __init__.py   build_registry(): the tools the agent gets (a new tool is added here)
  policies.py     what to do at the token limit: ask the user (AskUser) or wait (WaitAlone)
  guards.py       checks on an answer before it is accepted (no days that were not fetched)
  prompts.py      all texts sent to the model
  log.py          JSONL run log (RunLog)
  errors.py       exceptions and exit codes
```

## Agent loop

The agent calls the model repeatedly (one model call = one step) and executes the requested tools
until the model answers without a tool call. At most `MAX_STEPS` steps (default 30, so that a
question about all 14 mock days works even if the model fetches one day per step); hitting the
limit ends the run as an error (exit code 1, `error` event in the log).

Errors in a single step do not abort the run:

- a failing tool, invalid or missing arguments, or an unknown tool are reported back to the model
  as the tool result, so it can react;
- transient model errors (5xx, network, unparseable model output or garbled tool calls) are
  retried up to 3 times; if the model keeps producing garbled output, it is told so and asked
  again;
- an empty or cut-off answer is not accepted as a result: the model is told which days it has
  fetched so far and continues (it is not pushed to answer, which would make it invent data);
- an answer that talks about a day that was never fetched (dates are recognised in German,
  English and ISO notation) is not accepted either: the model is told to fetch those days first
  (at most twice per run, so the run still ends). This is a safety net, not a proof: it only sees
  dates the answer names explicitly, and does not check the answer against the question.

### Token limit (Groq free tier, 8,000 tokens/minute)

By default the agent handles the limit on its own, so every run ends without any input:

- it waits for the limit to reset (shown on stderr) and continues the same conversation, so the
  final answer covers the whole request;
- all waits of a run together may take up to `MAX_UNATTENDED_WAIT_S` (default 600 s). Beyond that
  the run ends with exit code 2, the endpoint's explanation of the limit and the partial results.

Asking the user instead is optional, via `ASK_ON_RATE_LIMIT`:

- `never` (default): wait as described above;
- `always`: at every longer pause (more than `MAX_AUTO_WAIT_S`, default 10 s) the results gathered
  so far are shown and the user is asked whether the rest should be processed. On `y` the agent
  waits and continues, on `n` (or no input) the run ends with exit code 2 and the partial results;
- `auto`: ask only when started in a terminal, otherwise wait.

Keeping token use low (every step sends the whole conversation again):

- the model is asked to request all days it needs in one step instead of one day per step;
- tool results only contain what an answer needs (no ids, no repeated dates, no empty fields);
- the model's reasoning is not sent back in later steps;
- once tool results are in the conversation, each request ends with a short reminder to answer in
  the language of the question (it is not stored in the history, so it is sent only once per request);
- for gpt-oss models `REASONING_EFFORT=low` is sent (reasoning counts as output); set it empty
  to disable. `MAX_COMPLETION_TOKENS` (default 1536) only caps runaway output.
- If an endpoint rejects one of these optional parameters (HTTP 400 naming it), the request is
  sent again without it (`max_completion_tokens` falls back to `max_tokens`).

### Exit codes

`0` answer, `1` error (including step limit), `2` stopped at the token limit with a partial result.

## Logs

Each run writes its own JSONL file to `logs/` (not committed) with the fields
`ts`, `run_id`, `event` (`user_task`, `tool_call`, `tool_result`, `final`, `error`),
`tool`, `args`, `ok`, `model` and `duration_ms`. Every run ends with exactly one `final`
(success, written after the answer was printed) or `error` event, so the log shows how the run
ended. Rate-limit waits, retries, nudges and the tokens used by the run are listed in
`args.notes` of that last event.
