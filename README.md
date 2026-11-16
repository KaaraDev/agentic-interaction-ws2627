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

## Agent loop

The agent calls the model repeatedly (one model call = one step) and executes the requested tools
until the model answers without a tool call. At most `MAX_STEPS` steps (default 30, so that a
question about all 14 mock days works even if the model fetches one day per step); hitting the
limit ends the run as an error (exit code 1, `error` event in the log).

Errors in a single step do not abort the run:

- a failing tool, invalid or missing arguments, or an unknown tool are reported back to the model
  as the tool result, so it can react;
- transient model errors (5xx, network, unparseable model output) are retried up to 3 times; if
  the model keeps producing unparseable output, it is told so and asked again;
- an empty or cut-off answer is not accepted as a result: the model is told which days it has
  fetched so far and continues (it is not pushed to answer, which would make it invent data).

### Token limit (Groq free tier, 8,000 tokens/minute)

- Short rate-limit waits (up to `MAX_AUTO_WAIT_S`, default 10 s) are waited out automatically.
- Longer waits **pause** the run.
  - *Interactive (stdin and stdout are a terminal):* the results gathered so far are shown on
    stderr and the user is asked whether the rest should be processed. On `y` the agent waits for
    the limit to reset and continues the same conversation, so the final answer covers the whole
    request. This can repeat as often as needed. On `n` the run ends with exit code 2 and the
    partial results.
  - *Unattended (e.g. automated tests, pipes, IDE run windows):* no question is asked; the agent
    waits for the reset and continues on its own, up to `MAX_UNATTENDED_WAIT_S` (default 180 s)
    per pause and 10 pauses. Beyond that it ends with exit code 2 and the partial results.
- `ASK_ON_RATE_LIMIT=auto|always|never` overrides the terminal detection (default `auto`).
- To use fewer tokens per request, `MAX_COMPLETION_TOKENS` (default 1536) caps the reserved output
  and, for gpt-oss models, `REASONING_EFFORT` (default `low`) is sent; set it empty to disable.

### Exit codes

`0` answer, `1` error (including step limit), `2` stopped at the token limit with a partial result.

## Logs

Each run writes its own JSONL file to `logs/` (not committed) with the fields
`ts`, `run_id`, `event` (`user_task`, `tool_call`, `tool_result`, `final`, `error`),
`tool`, `args`, `ok`, `model` and `duration_ms`. Every run ends with exactly one `final`
(success, written after the answer was printed) or `error` event, so the log shows how the run
ended. Rate-limit waits, retries and nudges are listed in `args.notes` of that last event.
