from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.chat.repository import ChatRepository
from src.domains.chat.schemas import (
    AuditConversationDetail,
    AuditConversationSummary,
    ConversationDetail,
    ConversationSummary,
    ConversationSync,
)
from src.domains.chat.service import ChatService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser, require_superadmin

router = APIRouter(prefix="/chat", tags=["chat"])

# No module gate — "Inicio" (the copilot) isn't behind a module, so neither
# is persisting/reading one's own conversations. The audit routes carry
# their own superadmin gate instead.


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> ChatService:
    return ChatService(ChatRepository(session))


@router.put("/conversations/{conversation_id}/sync", response_model=ConversationSummary)
async def sync_conversation(
    conversation_id: str,
    current_user: CurrentUser,
    data: ConversationSync,
    service: Annotated[ChatService, Depends(get_service)],
):
    return await service.sync_conversation(
        current_user.company_id, current_user.user_id, conversation_id, data.messages
    )


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    current_user: CurrentUser,
    service: Annotated[ChatService, Depends(get_service)],
):
    return await service.list_conversations(current_user.company_id, current_user.user_id)


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: str,
    current_user: CurrentUser,
    service: Annotated[ChatService, Depends(get_service)],
):
    conv, messages = await service.get_conversation(
        current_user.company_id, current_user.user_id, conversation_id
    )
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages,  # type: ignore[arg-type]
    )


# --- Superadmin audit (cross-company) ---

audit_router = APIRouter(
    prefix="/chat/audit", tags=["chat-audit"], dependencies=[Depends(require_superadmin)]
)


@audit_router.get("/conversations", response_model=list[AuditConversationSummary])
async def audit_list_conversations(
    _current_user: CurrentUser,
    service: Annotated[ChatService, Depends(get_service)],
    company_id: str | None = None,
    user_id: str | None = None,
):
    rows = await service.list_all_conversations(company_id=company_id, user_id=user_id)
    return [
        AuditConversationSummary(
            id=conv.id,
            title=conv.title,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            company_id=conv.company_id,
            user_id=conv.user_id,
            message_count=count,
        )
        for conv, count in rows
    ]


@audit_router.get("/conversations/{conversation_id}", response_model=AuditConversationDetail)
async def audit_get_conversation(
    conversation_id: str,
    _current_user: CurrentUser,
    service: Annotated[ChatService, Depends(get_service)],
):
    conv, messages = await service.get_conversation_any(conversation_id)
    return AuditConversationDetail(
        id=conv.id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        company_id=conv.company_id,
        user_id=conv.user_id,
        messages=messages,  # type: ignore[arg-type]
    )
