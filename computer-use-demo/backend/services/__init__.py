"""Session manager: handles concurrent sessions with per-session locking."""

import asyncio
import json
import logging
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import MessageModel, SessionModel, async_session_factory
from ..models import SessionConfig, ws_event

logger = logging.getLogger(__name__)


class SessionState:
    """Runtime state for an active session."""

    def __init__(self, session_id: str, config: SessionConfig):
        self.session_id = session_id
        self.config = config
        self.lock = asyncio.Lock()  # per-session lock, prevents race conditions
        self.cancel_event = asyncio.Event()
        self.sampling_task: asyncio.Task[Any] | None = None
        self.websockets: list[Any] = []  # connected WebSocket clients

    async def broadcast(self, event_type: str, data: Any = None):
        """Send event to all connected WebSocket clients."""
        msg = ws_event(event_type, data)
        dead: list[Any] = []
        for ws in self.websockets:
            try:
                await ws.send_text(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.websockets.remove(ws)

    @property
    def is_running(self) -> bool:
        return self.sampling_task is not None and not self.sampling_task.done()


class SessionManager:
    """Manages all active sessions in memory, backed by database."""

    def __init__(self):
        self._sessions: dict[str, SessionState] = {}
        self._global_lock = asyncio.Lock()

    async def create_session(self, name: str, config: SessionConfig) -> tuple[SessionState, dict[str, Any]]:
        """Create a new session in DB and memory.

        Returns (state, session_dict) where session_dict has id, name, status, config, created_at, updated_at.
        """
        import uuid

        session_id = str(uuid.uuid4())
        config_dict = config.model_dump()

        async with async_session_factory() as db:
            db_session = SessionModel(
                id=session_id,
                name=name,
                status="active",
                config_json=json.dumps(config_dict),
            )
            db.add(db_session)
            await db.commit()
            await db.refresh(db_session)
            session_dict = {
                "id": db_session.id,
                "name": db_session.name,
                "status": db_session.status,
                "config": json.loads(db_session.config_json) if db_session.config_json else None,
                "created_at": db_session.created_at.isoformat(),
                "updated_at": db_session.updated_at.isoformat(),
            }

        state = SessionState(session_id, config)
        async with self._global_lock:
            self._sessions[session_id] = state

        logger.info(f"Created session {session_id}: {name}")
        return state, session_dict

    async def get_session(self, session_id: str) -> SessionState | None:
        """Get a running session state."""
        async with self._global_lock:
            return self._sessions.get(session_id)

    async def get_or_load_session(self, session_id: str) -> SessionState | None:
        """Get session from memory or load from DB."""
        state = await self.get_session(session_id)
        if state:
            return state

        # Load from DB
        async with async_session_factory() as db:
            result = await db.execute(
                select(SessionModel).where(SessionModel.id == session_id)
            )
            db_session = result.scalar_one_or_none()
            if db_session is None:
                return None
            config_dict = json.loads(db_session.config_json) if db_session.config_json else {}
            config = SessionConfig(**config_dict)
            state = SessionState(session_id, config)
            async with self._global_lock:
                self._sessions[session_id] = state
            return state

    async def list_sessions(self, status: str | None = None) -> list[dict[str, Any]]:
        """List all sessions from DB."""
        async with async_session_factory() as db:
            stmt = select(SessionModel).order_by(SessionModel.created_at.desc())
            if status:
                stmt = stmt.where(SessionModel.status == status)
            result = await db.execute(stmt)
            sessions = result.scalars().all()
            return [
                {
                    "id": s.id,
                    "name": s.name,
                    "status": s.status,
                    "config": json.loads(s.config_json) if s.config_json else None,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                }
                for s in sessions
            ]

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session from DB and memory."""
        async with self._global_lock:
            state = self._sessions.pop(session_id, None)
            if state:
                state.cancel_event.set()
                if state.sampling_task and not state.sampling_task.done():
                    state.sampling_task.cancel()

        async with async_session_factory() as db:
            result = await db.execute(
                delete(SessionModel).where(SessionModel.id == session_id)
            )
            await db.commit()
            return result.rowcount > 0  # type: ignore[union-attr]

    async def update_session_status(self, session_id: str, status: str):
        """Update session status in DB."""
        async with async_session_factory() as db:
            await db.execute(
                update(SessionModel)
                .where(SessionModel.id == session_id)
                .values(status=status)
            )
            await db.commit()

    async def save_message(
        self, session_id: str, role: str, content: Any, tool_use_id: str | None = None
    ):
        """Persist a message to DB."""
        async with async_session_factory() as db:
            msg = MessageModel(
                session_id=session_id,
                role=role,
                content_json=json.dumps(content),
                tool_use_id=tool_use_id,
            )
            db.add(msg)
            await db.commit()

    async def get_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get all messages for a session from DB."""
        async with async_session_factory() as db:
            result = await db.execute(
                select(MessageModel)
                .where(MessageModel.session_id == session_id)
                .order_by(MessageModel.created_at)
            )
            messages = result.scalars().all()
            return [
                {
                    "id": m.id,
                    "session_id": m.session_id,
                    "role": m.role,
                    "content": json.loads(m.content_json),
                    "tool_use_id": m.tool_use_id,
                    "created_at": m.created_at.isoformat(),
                }
                for m in messages
            ]

    async def get_api_messages(self, session_id: str) -> list[dict[str, Any]]:
        """Get messages formatted for Claude API (role + content only)."""
        msgs = await self.get_messages(session_id)
        return [{"role": m["role"], "content": m["content"]} for m in msgs]

    async def cleanup(self):
        """Cancel all running sampling tasks."""
        async with self._global_lock:
            for state in self._sessions.values():
                state.cancel_event.set()
                if state.sampling_task and not state.sampling_task.done():
                    state.sampling_task.cancel()
            self._sessions.clear()


# Global singleton
session_manager = SessionManager()
