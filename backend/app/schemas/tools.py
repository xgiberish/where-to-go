from typing import Any

from pydantic import BaseModel


class ToolInput(BaseModel):
    tool_name: str
    inputs: dict[str, Any]


class ToolOutput(BaseModel):
    tool_name: str
    result: Any
    error: str | None = None
