"""SQLAlchemy database models and session management."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from .config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class SessionModel(Base):
    """Represents a user session / conversation."""

    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False, default="New Session")
    status = Column(String(20), nullable=False, default="active")  # active, completed, error
    config_json = Column(Text, nullable=True)  # JSON: model, provider, tool_version, etc.
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    messages = relationship("MessageModel", back_populates="session", cascade="all, delete-orphan",
                            order_by="MessageModel.created_at")

    __table_args__ = (
        Index("idx_sessions_status", "status"),
        Index("idx_sessions_created_at", "created_at"),
    )


class MessageModel(Base):
    """Represents a single chat message within a session."""

    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, tool
    content_json = Column(Text, nullable=False)  # JSON-serialized message content
    tool_use_id = Column(String(64), nullable=True)  # for tool results
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    session = relationship("SessionModel", back_populates="messages")

    __table_args__ = (
        Index("idx_messages_session_id", "session_id"),
        Index("idx_messages_created_at", "created_at"),
    )


async def init_db():
    """Create all tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Get an async database session."""
    async with async_session_factory() as session:
        yield session
