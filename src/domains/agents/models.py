import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import AutoString, Column, Field, SQLModel, UniqueConstraint

# Keys match src/lib/data.ts's AgentKey on the frontend: compras (Yaco),
# cobros (Mara), stock (Inti), precios (Kuri), catalogo (Khipu).
AGENT_KEYS = ("compras", "cobros", "stock", "precios", "catalogo")


class AgentConfig(SQLModel, table=True):
    __tablename__ = "agent_configs"
    __table_args__ = (UniqueConstraint("company_id", "agent_key", name="uq_agent_configs_company_agent"),)

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    agent_key: str = Field(max_length=20)
    enabled: bool = Field(default=True)
    autonomy: str = Field(default="ask", max_length=10)  # "ask" | "auto"
    auto_limit: Optional[float] = Field(default=None)


class AgentAlert(SQLModel, table=True):
    __tablename__ = "agent_alerts"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    agent_key: str = Field(max_length=20)
    title: str = Field(max_length=200)
    body: str
    # List of {"k": label, "v": value} shown as context chips in the UI.
    context: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSONB))
    # What executing this alert will do, e.g. {"tool": "create_purchase", "args": {...}}
    proposed_action: dict[str, Any] = Field(sa_column=Column(JSONB))
    status: str = Field(default="pending", sa_type=AutoString)  # pending|approved|rejected|auto_applied|failed
    result: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSONB))
    # LangGraph thread id so approving/rejecting later resumes the exact
    # paused graph run instead of starting a new one.
    thread_id: str = Field(max_length=36)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
    resolved_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))


class PendingAgentTrigger(SQLModel, table=True):
    """A breadcrumb a business action leaves behind (e.g. a sale dropped
    stock below the minimum) so the next agent sweep reacts to it, without
    the request that caused it having to wait on an LLM call."""

    __tablename__ = "pending_agent_triggers"

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True, max_length=36)
    company_id: str = Field(foreign_key="companies.id", max_length=36, index=True)
    agent_key: str = Field(max_length=20)
    context: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), sa_type=DateTime(timezone=True))
    processed_at: Optional[datetime] = Field(default=None, sa_type=DateTime(timezone=True))
