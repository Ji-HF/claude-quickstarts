"""Session management API routes."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException

from ..models import (
    ChatRequest,
    MessageListResponse,
    MessageResponse,
    SessionCreate,
    SessionListResponse,
    SessionResponse,
)
from ..services import session_manager
from ..services.sampling import run_sampling_loop

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=201)
async def create_session(req: SessionCreate):
    """Create a new session."""
    state, session_dict = await session_manager.create_session(req.name, req.config)
    return SessionResponse(**session_dict)


@router.get("", response_model=SessionListResponse)
async def list_sessions(status: str | None = None):
    """List all sessions."""
    sessions = await session_manager.list_sessions(status=status)
    return SessionListResponse(
        sessions=[SessionResponse(**s) for s in sessions],
        total=len(sessions),
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get a session by ID."""
    sessions = await session_manager.list_sessions()
    for s in sessions:
        if s["id"] == session_id:
            return SessionResponse(**s)
    raise HTTPException(status_code=404, detail="Session not found")


@router.delete("/{session_id}", status_code=204)
async def delete_session(session_id: str):
    """Delete a session and cancel any running sampling loop."""
    success = await session_manager.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")


@router.post("/{session_id}/chat")
async def send_message(session_id: str, req: ChatRequest):
    """Send a user message to the session, starting the sampling loop.

    The response is streamed via WebSocket at /ws/sessions/{session_id}.
    This endpoint returns immediately with an acknowledgement.
    """
    state = await session_manager.get_or_load_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if state.is_running:
        raise HTTPException(status_code=409, detail="Session is already processing a message")

    # Save user message
    user_content = [{"type": "text", "text": req.message}]
    await session_manager.save_message(session_id, "user", user_content)

    # Get all messages for the API call
    api_messages = await session_manager.get_api_messages(session_id)
    original_message_count = len(api_messages)

    # Start sampling loop in background
    cfg = state.config

    # Apply environment variable defaults for provider & model
    import os as _os
    # API_PROVIDER env var takes priority over session config
    effective_provider = _os.getenv("API_PROVIDER") or cfg.provider or "anthropic"
    effective_model = cfg.model or (
        _os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
        if effective_provider == "deepseek"
        else "claude-sonnet-4-20250514"
    )
    effective_api_key = cfg.api_key or (
        _os.getenv("DEEPSEEK_API_KEY", "")
        if effective_provider == "deepseek"
        else _os.getenv("ANTHROPIC_API_KEY", "")
    )

    async def _run():
        try:
            async with state.lock:  # per-session lock prevents concurrent access
                await state.broadcast("status", {"message": "Starting agent loop...", "phase": "starting"})
                updated_messages = await run_sampling_loop(
                    session_id=session_id,
                    model=effective_model,
                    provider=effective_provider,
                    api_key=effective_api_key,
                    messages=api_messages,
                    tool_version=cfg.tool_version,  # type: ignore[arg-type]
                    max_tokens=cfg.max_tokens,
                    only_n_most_recent_images=cfg.only_n_most_recent_images,
                    system_prompt_suffix=cfg.custom_system_prompt,
                    thinking_mode=cfg.thinking_mode,
                    thinking_effort=cfg.thinking_effort,
                    thinking_budget=cfg.thinking_budget,
                    token_efficient_tools_beta=cfg.token_efficient_tools_beta,
                    broadcast=state.broadcast,
                    cancel_event=state.cancel_event,
                )
                # Save only NEW assistant + tool messages to DB
                new_messages = updated_messages[original_message_count:]
                for msg in new_messages:
                    role = msg["role"]
                    content = msg["content"]
                    await session_manager.save_message(session_id, role, content)

                await session_manager.update_session_status(session_id, "active")
                await state.broadcast("done", {"message": "Agent finished"})
        except asyncio.CancelledError:
            await state.broadcast("cancelled", {"message": "Session cancelled"})
            await session_manager.update_session_status(session_id, "active")
        except Exception as e:
            logger.exception(f"Error in sampling loop for session {session_id}")
            await state.broadcast("error", {"message": str(e)})
            await session_manager.update_session_status(session_id, "error")

    state.cancel_event.clear()
    state.sampling_task = asyncio.create_task(_run())

    return {"status": "accepted", "session_id": session_id, "message": "Message received, agent is processing"}


@router.post("/{session_id}/cancel")
async def cancel_session(session_id: str):
    """Cancel the currently running sampling loop for a session."""
    state = await session_manager.get_session(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if not state.is_running:
        raise HTTPException(status_code=409, detail="No active loop to cancel")
    state.cancel_event.set()
    return {"status": "cancelled", "session_id": session_id}


@router.get("/{session_id}/messages", response_model=MessageListResponse)
async def get_messages(session_id: str):
    """Get all messages for a session."""
    messages = await session_manager.get_messages(session_id)
    return MessageListResponse(
        messages=[MessageResponse(**m) for m in messages],
        session_id=session_id,
    )
