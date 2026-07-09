from datetime import datetime

from pydantic import BaseModel


class AiUsageEventCreate(BaseModel):
    source: str
    provider: str = "openai"
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cached_input_tokens: int | None = None
    audio_seconds: float | None = None


class AiUsageEventRead(BaseModel):
    id: int
    company_id: str
    source: str
    provider: str
    model: str
    input_tokens: int | None
    output_tokens: int | None
    cached_input_tokens: int | None
    audio_seconds: float | None
    created_at: datetime

    model_config = {"from_attributes": True}
