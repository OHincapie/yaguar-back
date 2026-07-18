import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import Column, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

# Persistence for the "Inicio" copilot chat. Until now the conversation
# lived only in the browser's useChat state (gone on refresh) — this is the
# system of record for two purposes: the user's own history, and a
# platform-superadmin audit trail across every company. Written server-side
# from the chat route's onFinish (not trusted from the client), so a client
# can't skip writing an audit record.


class ChatConversation(SQLModel, table=True):
    __tablename__ = "chat_conversations"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    user_id: str = Field(foreign_key="users.id", max_length=36, index=True)
    # Derived from the first user message the first time the conversation is
    # saved; null only for the brief window before that.
    title: Optional[str] = Field(default=None, max_length=200)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True), index=True
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    # The client-generated UIMessage id, reused as the PK so re-saving the
    # whole conversation each turn upserts by id instead of duplicating —
    # and a tool "continuation" that extends an existing assistant message
    # updates it in place rather than creating a second row.
    id: str = Field(primary_key=True, max_length=64)
    conversation_id: str = Field(foreign_key="chat_conversations.id", max_length=36, index=True)
    role: str = Field(max_length=20)
    # The full AI SDK UIMessage `parts` array (text, tool calls, tool
    # results, approvals, and file attachments inline as data URLs) — stored
    # verbatim so the audit view can reconstruct exactly what happened,
    # including which action the copilot proposed and whether it was
    # approved.
    parts: list[Any] = Field(default_factory=list, sa_column=Column(JSONB))
    # Position within the conversation (index in the message list at save
    # time) — the stable ordering key, since created_at can collide when a
    # turn writes several messages in the same millisecond.
    seq: int = Field(default=0, index=True)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True)
    )
