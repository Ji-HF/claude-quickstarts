"""Pydantic models for API request/response schemas."""

import json
from typing import Any

from pydantic import BaseModel, Field


# ─── Session ─────────────────────────────────────────────────────────────────

class SessionConfig(BaseModel):
    model: str = ""
    provider: str = ""  # anthropic, bedrock, vertex, deepseek
    api_key: str = ""
    tool_version: str = "computer_use_20251124"
    max_tokens: int = 16384
    only_n_most_recent_images: int = 3
    custom_system_prompt: str = ""
    thinking_mode: str = "adaptive"  # adaptive, extended, off
    thinking_effort: str = "medium"  # low, medium, high, max
    thinking_budget: int | None = None
    token_efficient_tools_beta: bool = False


class SessionCreate(BaseModel):
    name: str = "New Session"
    config: SessionConfig = Field(default_factory=SessionConfig)


class SessionResponse(BaseModel):
    id: str
    name: str
    status: str
    config: dict[str, Any] | None = None
    created_at: str  # ISO 8601 string
    updated_at: str  # ISO 8601 string

    class Config:
        from_attributes = True


class SessionListResponse(BaseModel):
    sessions: list[SessionResponse]
    total: int


# ─── Messages ────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: Any  # parsed JSON content
    tool_use_id: str | None = None
    created_at: str  # ISO 8601 string

    class Config:
        from_attributes = True


class MessageListResponse(BaseModel):
    messages: list[MessageResponse]
    session_id: str


# ─── WebSocket Events ────────────────────────────────────────────────────────

class WSEvent(BaseModel):
    """Base WebSocket event."""
    type: str
    data: Any = None


def ws_event(event_type: str, data: Any = None) -> str:
    """Serialize a WebSocket event to JSON string."""
    return json.dumps({"type": event_type, "data": data})
