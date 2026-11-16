"""Tool registry: tools describe themselves to the model and are executed by name.

A new tool is one `Tool(...)` added in tools/__init__.py; the agent loop does not change.
"""
import json
from dataclasses import dataclass
from typing import Callable

from ..errors import ToolError

MAX_RESULT_CHARS = 4000  # keeps a single tool result from eating the token budget


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict           # JSON schema of the arguments
    func: Callable[..., str]   # called with the arguments as keyword arguments, returns text

    def schema(self) -> dict:
        return {"type": "function",
                "function": {"name": self.name, "description": self.description, "parameters": self.parameters}}


@dataclass(frozen=True)
class ToolResult:
    tool: str
    args: dict
    content: str  # what the model gets to see
    ok: bool


class ToolRegistry:
    def __init__(self, tools: list[Tool]):
        self._tools = {tool.name: tool for tool in tools}

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        return [tool.schema() for tool in self._tools.values()]

    def execute(self, name: str, raw_args: str | None) -> ToolResult:
        """Run one tool call. Never raises: every problem becomes an error result for the model."""
        try:
            args = json.loads(raw_args or '{}')
        except json.JSONDecodeError as e:
            return self._error(name, {}, f"Arguments are not valid JSON: {e}")
        if not isinstance(args, dict):
            return self._error(name, {}, "Tool arguments must be a JSON object.")

        tool = self._tools.get(name)
        if tool is None:
            return self._error(name, args, f"Unknown tool {name}")
        try:
            content = tool.func(**args)
        except ToolError as e:
            return self._error(name, args, str(e))
        except TypeError as e:  # missing or unexpected argument names
            return self._error(name, args, f"Bad arguments for {name}: {e}")
        except Exception as e:
            return self._error(name, args, f"{type(e).__name__}: {e}")

        if len(content) > MAX_RESULT_CHARS:
            content = content[:MAX_RESULT_CHARS] + '... [truncated]'
        return ToolResult(name, args, content, ok=True)

    @staticmethod
    def _error(name: str, args: dict, message: str) -> ToolResult:
        return ToolResult(name, args, json.dumps({"error": message}), ok=False)
