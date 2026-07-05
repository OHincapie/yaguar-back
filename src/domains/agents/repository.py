from datetime import datetime, timezone

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.accounts.models import Company
from src.domains.agents.models import AGENT_KEYS, AgentAlert, AgentConfig, PendingAgentTrigger


class AgentRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def list_company_ids(self) -> list[str]:
        result = await self.session.exec(select(Company.id))  # type: ignore
        return result.all()

    # --- config -----------------------------------------------------

    async def get_configs(self, company_id: str) -> list[AgentConfig]:
        result = await self.session.exec(  # type: ignore
            select(AgentConfig).where(AgentConfig.company_id == company_id)
        )
        existing = {c.agent_key: c for c in result.all()}
        # Agents added after a company already existed won't have a config
        # row yet — default them to enabled/ask rather than 404ing.
        missing = [AgentConfig(company_id=company_id, agent_key=k) for k in AGENT_KEYS if k not in existing]
        return list(existing.values()) + missing

    async def get_config(self, company_id: str, agent_key: str) -> AgentConfig:
        result = await self.session.exec(  # type: ignore
            select(AgentConfig).where(AgentConfig.company_id == company_id, AgentConfig.agent_key == agent_key)
        )
        config = result.first()
        return config or AgentConfig(company_id=company_id, agent_key=agent_key)

    async def upsert_config(self, config: AgentConfig) -> AgentConfig:
        self.session.add(config)
        await self.session.commit()
        await self.session.refresh(config)
        return config

    # --- alerts -------------------------------------------------------

    async def create_alert(self, alert: AgentAlert) -> AgentAlert:
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    async def get_alert(self, company_id: str, alert_id: str) -> AgentAlert | None:
        result = await self.session.exec(  # type: ignore
            select(AgentAlert).where(AgentAlert.company_id == company_id, AgentAlert.id == alert_id)
        )
        return result.first()

    async def list_alerts(self, company_id: str, status: str | None = None) -> list[AgentAlert]:
        query = select(AgentAlert).where(AgentAlert.company_id == company_id)
        if status:
            query = query.where(AgentAlert.status == status)
        result = await self.session.exec(query.order_by(AgentAlert.created_at.desc()))  # type: ignore
        return result.all()

    async def update_alert(self, alert: AgentAlert) -> AgentAlert:
        self.session.add(alert)
        await self.session.commit()
        await self.session.refresh(alert)
        return alert

    # --- triggers -------------------------------------------------------

    async def create_trigger(self, trigger: PendingAgentTrigger) -> PendingAgentTrigger:
        self.session.add(trigger)
        await self.session.commit()
        await self.session.refresh(trigger)
        return trigger

    async def get_unprocessed_triggers(self, company_id: str, agent_key: str) -> list[PendingAgentTrigger]:
        result = await self.session.exec(  # type: ignore
            select(PendingAgentTrigger).where(
                PendingAgentTrigger.company_id == company_id,
                PendingAgentTrigger.agent_key == agent_key,
                PendingAgentTrigger.processed_at.is_(None),  # type: ignore
            )
        )
        return result.all()

    async def get_companies_with_pending_triggers(self) -> list[tuple[str, str]]:
        """Distinct (company_id, agent_key) pairs that have at least one
        unprocessed trigger, so the sweep only wakes up agents with
        something new to react to."""
        result = await self.session.exec(  # type: ignore
            select(PendingAgentTrigger.company_id, PendingAgentTrigger.agent_key)
            .where(PendingAgentTrigger.processed_at.is_(None))  # type: ignore
            .distinct()
        )
        return result.all()

    async def mark_triggers_processed(self, triggers: list[PendingAgentTrigger]) -> None:
        now = datetime.now(timezone.utc)
        for trigger in triggers:
            trigger.processed_at = now
            self.session.add(trigger)
        await self.session.commit()
