from src.domains.ai_usage.models import AiUsageEvent
from src.domains.ai_usage.repository import AiUsageRepository
from src.domains.ai_usage.schemas import AiUsageEventCreate


class AiUsageService:
    def __init__(self, repo: AiUsageRepository):
        self.repo = repo

    async def log_event(self, company_id: str, data: AiUsageEventCreate) -> AiUsageEvent:
        event = AiUsageEvent(
            company_id=company_id,
            source=data.source,
            provider=data.provider,
            model=data.model,
            input_tokens=data.input_tokens,
            output_tokens=data.output_tokens,
            cached_input_tokens=data.cached_input_tokens,
            audio_seconds=data.audio_seconds,
        )
        return await self.repo.create(event)
