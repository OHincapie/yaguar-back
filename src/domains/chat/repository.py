from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.chat.models import ChatConversation, ChatMessage


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_conversation(self, conversation_id: str) -> ChatConversation | None:
        result = await self.session.exec(  # type: ignore
            select(ChatConversation).where(ChatConversation.id == conversation_id)
        )
        return result.first()

    async def add_conversation(self, conversation: ChatConversation) -> ChatConversation:
        self.session.add(conversation)
        await self.session.commit()
        await self.session.refresh(conversation)
        return conversation

    async def list_conversations_for_user(self, company_id: str, user_id: str) -> list[ChatConversation]:
        result = await self.session.exec(  # type: ignore
            select(ChatConversation)
            .where(ChatConversation.company_id == company_id, ChatConversation.user_id == user_id)
            .order_by(ChatConversation.updated_at.desc())  # type: ignore[attr-defined]
        )
        return list(result.all())

    async def list_messages(self, conversation_id: str) -> list[ChatMessage]:
        result = await self.session.exec(  # type: ignore
            select(ChatMessage)
            .where(ChatMessage.conversation_id == conversation_id)
            .order_by(ChatMessage.seq)  # type: ignore[arg-type]
        )
        return list(result.all())

    async def get_message(self, message_id: str) -> ChatMessage | None:
        result = await self.session.exec(  # type: ignore
            select(ChatMessage).where(ChatMessage.id == message_id)
        )
        return result.first()

    async def upsert_messages(self, conversation_id: str, rows: list[dict]) -> None:
        """rows: [{id, role, parts, seq}] — updates existing rows by id
        (parts/seq) and inserts new ones, so re-saving the whole conversation
        each turn is idempotent."""
        for row in rows:
            existing = await self.get_message(row["id"])
            if existing:
                existing.parts = row["parts"]
                existing.role = row["role"]
                existing.seq = row["seq"]
                self.session.add(existing)
            else:
                self.session.add(
                    ChatMessage(
                        id=row["id"],
                        conversation_id=conversation_id,
                        role=row["role"],
                        parts=row["parts"],
                        seq=row["seq"],
                    )
                )
        await self.session.commit()

    async def commit(self) -> None:
        await self.session.commit()

    # --- Superadmin audit (cross-company) ---

    async def list_all_conversations(
        self, limit: int = 200, company_id: str | None = None, user_id: str | None = None
    ) -> list[tuple[ChatConversation, int]]:
        count_subq = (
            select(ChatMessage.conversation_id, func.count().label("n"))
            .group_by(ChatMessage.conversation_id)
            .subquery()
        )
        query = (
            select(ChatConversation, func.coalesce(count_subq.c.n, 0))
            .outerjoin(count_subq, count_subq.c.conversation_id == ChatConversation.id)
            .order_by(ChatConversation.updated_at.desc())  # type: ignore[attr-defined]
            .limit(limit)
        )
        if company_id:
            query = query.where(ChatConversation.company_id == company_id)
        if user_id:
            query = query.where(ChatConversation.user_id == user_id)
        result = await self.session.exec(query)  # type: ignore
        return [(row[0], row[1]) for row in result.all()]
