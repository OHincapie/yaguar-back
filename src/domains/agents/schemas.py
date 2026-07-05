from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AgentConfigRead(BaseModel):
    agent_key: str
    enabled: bool
    autonomy: str
    auto_limit: float | None

    model_config = {"from_attributes": True}


class AgentConfigUpdate(BaseModel):
    enabled: bool | None = None
    autonomy: str | None = None
    auto_limit: float | None = None


class AgentAlertRead(BaseModel):
    id: str
    agent_key: str
    title: str
    body: str
    context: list[dict[str, Any]]
    status: str
    result: dict[str, Any] | None
    created_at: datetime
    resolved_at: datetime | None

    model_config = {"from_attributes": True}
