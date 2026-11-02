# agentic-interaction-ws2627

Calendar agent for Exercise 1: the model calls one tool (`get_calendar_day`) that reads the
appointments of a day from `{DATA_BASE_URL}/calendar/{YYYY-MM-DD}.json` and then answers.

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

```bash
python -m agent "Was steht am 29.10.2026 im Kalender?"
```

The answer is printed to standard output (exit code 0).

## Logs

Each run writes its own JSONL file to `logs/` (not committed) with the fields
`ts`, `run_id`, `event` (`user_task`, `tool_call`, `tool_result`, `final`, `error`),
`tool`, `args`, `ok`, `model` and `duration_ms`.
