from datetime import datetime, timezone
from typing import Any

from src.domains.chat.models import ChatConversation
from src.domains.chat.repository import ChatRepository
from src.domains.chat.schemas import ChatMessageIn
from src.shared.middleware.errors import ForbiddenError, NotFoundError


def _derive_title(messages: list[ChatMessageIn]) -> str | None:
    """First user message's text, trimmed — the conversation's label in the
    history list. Falls back to None if the first turn has no plain text
    (e.g. an attachment-only message)."""
    for m in messages:
        if m.role != "user":
            continue
        for part in m.parts:
            if isinstance(part, dict) and part.get("type") == "text" and part.get("text"):
                text = " ".join(str(part["text"]).split())
                return text[:80]
        return None
    return None


class ChatService:
    def __init__(self, repo: ChatRepository):
        self.repo = repo

    async def sync_conversation(
        self, company_id: str, user_id: str, conversation_id: str, messages: list[ChatMessageIn]
    ) -> ChatConversation:
        conv = await self.repo.get_conversation(conversation_id)
        if conv is None:
            conv = ChatConversation(
                id=conversation_id,
                company_id=company_id,
                user_id=user_id,
                title=_derive_title(messages),
            )
            conv = await self.repo.add_conversation(conv)
        elif conv.company_id != company_id or conv.user_id != user_id:
            # The id is a client-generated UUID; refuse to let one user write
            # into another user's (or company's) conversation by guessing it.
            raise ForbiddenError("This conversation belongs to someone else")

        rows = [{"id": m.id, "role": m.role, "parts": m.parts, "seq": i} for i, m in enumerate(messages)]
        await self.repo.upsert_messages(conversation_id, rows)

        conv.updated_at = datetime.now(timezone.utc)
        if not conv.title:
            conv.title = _derive_title(messages)
        self.repo.session.add(conv)
        await self.repo.commit()
        return conv

    async def list_conversations(self, company_id: str, user_id: str) -> list[ChatConversation]:
        return await self.repo.list_conversations_for_user(company_id, user_id)

    async def get_conversation(self, company_id: str, user_id: str, conversation_id: str):
        conv = await self.repo.get_conversation(conversation_id)
        if conv is None or conv.company_id != company_id or conv.user_id != user_id:
            # Same 404 whether it doesn't exist or isn't yours — don't leak
            # the existence of another user's conversation.
            raise NotFoundError("Conversation not found")
        messages = await self.repo.list_messages(conversation_id)
        return conv, messages

    # --- Superadmin audit ---

    async def list_all_conversations(
        self, company_id: str | None = None, user_id: str | None = None
    ) -> list[tuple[ChatConversation, int]]:
        return await self.repo.list_all_conversations(company_id=company_id, user_id=user_id)

    async def get_conversation_any(self, conversation_id: str):
        conv = await self.repo.get_conversation(conversation_id)
        if conv is None:
            raise NotFoundError("Conversation not found")
        messages = await self.repo.list_messages(conversation_id)
        return conv, messages
