from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.ai_usage.repository import AiUsageRepository
from src.domains.ai_usage.schemas import AiUsageEventCreate, AiUsageEventRead
from src.domains.ai_usage.service import AiUsageService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser

router = APIRouter(prefix="/ai-usage", tags=["ai-usage"])

# No module gate — the chat itself isn't gated behind a module (every
# authenticated member can use "Inicio"), so logging its own usage
# shouldn't require one either.


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> AiUsageService:
    return AiUsageService(AiUsageRepository(session))


@router.post("", response_model=AiUsageEventRead, status_code=201)
async def log_usage(
    current_user: CurrentUser,
    data: AiUsageEventCreate,
    service: Annotated[AiUsageService, Depends(get_service)],
):
    return await service.log_event(current_user.company_id, data)
