from datetime import datetime
from typing import Any

from pydantic import BaseModel


class ChatMessageIn(BaseModel):
    id: str
    role: str
    parts: list[Any] = []


class ConversationSync(BaseModel):
    # The client owns the conversation id (a UUID it generates when starting
    # a fresh chat), so the first sync both creates the conversation and
    # writes its messages — no separate "create" round trip before the
    # stream starts.
    messages: list[ChatMessageIn]


class ChatMessageRead(BaseModel):
    id: str
    role: str
    parts: list[Any]
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationSummary(BaseModel):
    id: str
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetail(ConversationSummary):
    messages: list[ChatMessageRead]


# Adds the tenant/user identity a cross-company audit view needs — the
# per-user history endpoints never expose these (they're already scoped to
# the caller).
class AuditConversationSummary(ConversationSummary):
    company_id: str
    user_id: str
    message_count: int


class AuditConversationDetail(ConversationDetail):
    company_id: str
    user_id: str
