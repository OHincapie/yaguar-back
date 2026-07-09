from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime
from sqlmodel import Field, SQLModel

# Raw usage, not a dollar amount — token/model prices change, and baking a
# cost into each row would mean either being permanently wrong when prices
# move or needing a backfill migration every time OpenAI repriced something.
# Cost should be computed at query time (dashboard/report, not built yet)
# from a small pricing table keyed by the model name stored here.


class AiUsageEvent(SQLModel, table=True):
    __tablename__ = "ai_usage_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    # Which feature made the call — "chat", "transcribe", "agent:inti", etc.
    # Free text on purpose (new sources shouldn't need a migration to add).
    source: str = Field(max_length=50, index=True)
    provider: str = Field(max_length=30, default="openai")
    model: str = Field(max_length=100, index=True)
    input_tokens: Optional[int] = Field(default=None)
    output_tokens: Optional[int] = Field(default=None)
    # OpenAI prices cached input tokens lower — worth keeping separate from
    # input_tokens rather than folded in, so cost math can be accurate.
    cached_input_tokens: Optional[int] = Field(default=None)
    # Transcription is billed by audio duration, not tokens — null for
    # everything except source="transcribe".
    audio_seconds: Optional[float] = Field(default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True), index=True
    )
