"""Tools available to the agent."""
from ..config import Config
from .base import Tool, ToolRegistry, ToolResult
from .calendar import calendar_tool


def build_registry(config: Config) -> ToolRegistry:
    return ToolRegistry([
        calendar_tool(config.data_base_url),
    ])


__all__ = ['Tool', 'ToolRegistry', 'ToolResult', 'build_registry']
