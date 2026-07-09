from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.ai_usage.models import AiUsageEvent


class AiUsageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, event: AiUsageEvent) -> AiUsageEvent:
        self.session.add(event)
        await self.session.commit()
        await self.session.refresh(event)
        return event
