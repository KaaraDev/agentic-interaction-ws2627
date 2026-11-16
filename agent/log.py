"""Run log: one JSONL file per run in logs/, one line per event.

Events (interface specification): user_task, tool_call, tool_result, final, error.
Fields: ts, run_id, event, tool, args, ok, model, duration_ms.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parent.parent / 'logs'


class RunLog:
    def __init__(self, model: str | None, log_dir: Path = LOG_DIR):
        self.model = model
        self.run_id = uuid.uuid4().hex[:8]
        log_dir.mkdir(exist_ok=True)
        stamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self.path = log_dir / f'{stamp}_{self.run_id}.jsonl'
        # Waits, retries and nudges are no events of their own (the specification fixes the event
        # names); they are collected here and written into the args of the final / error event.
        self.notes: list[str] = []

    def note(self, text: str) -> None:
        self.notes.append(text)

    def write(self, event: str, **fields) -> None:
        entry = {
            'ts': datetime.now(timezone.utc).isoformat(),
            'run_id': self.run_id,
            'event': event,
            'model': self.model,
            **fields,
        }
        with open(self.path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
