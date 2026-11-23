"""Tools available to the agent."""
from ..config import Config
from .base import Tool, ToolRegistry, ToolResult
from .calendar import calendar_tool
from .transit import transit_tool
from .weather import weather_tool


def build_registry(config: Config) -> ToolRegistry:
    return ToolRegistry([
        calendar_tool(config.data_base_url),
        weather_tool(config.data_base_url),
        transit_tool(config.data_base_url),
    ])


__all__ = ['Tool', 'ToolRegistry', 'ToolResult', 'build_registry']
