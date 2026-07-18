from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.agents.detectors import (
    detect_catalog_issues,
    detect_collections_issues,
    detect_margin_issues,
    detect_reorder_needs,
    detect_stock_issues,
)
from src.domains.agents.graph import resume_proposal, run_proposal
from src.domains.agents.models import AgentAlert, AgentConfig
from src.domains.agents.repository import AgentRepository
from src.domains.agents.schemas import AgentConfigUpdate
from src.shared.middleware.errors import BusinessError, NotFoundError

# Which detector feeds which agent. Adding Yaco/Mara/Kuri means adding a
# key here (and their detector module) — sweep()/sweep_all() don't change.
DETECTORS = {
    "compras": detect_reorder_needs,
    "stock": detect_stock_issues,
    "precios": detect_margin_issues,
    "cobros": detect_collections_issues,
    "catalogo": detect_catalog_issues,
}


class AgentService:
    def __init__(self, repo: AgentRepository, session: AsyncSession):
        self.repo = repo
        self.session = session

    async def list_configs(self, company_id: str) -> list[AgentConfig]:
        return await self.repo.get_configs(company_id)

    async def update_config(self, company_id: str, agent_key: str, data: AgentConfigUpdate) -> AgentConfig:
        config = await self.repo.get_config(company_id, agent_key)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(config, field, value)
        return await self.repo.upsert_config(config)

    async def list_alerts(self, company_id: str, status: str | None = None) -> list[AgentAlert]:
        return await self.repo.list_alerts(company_id, status)

    async def approve_alert(self, company_id: str, alert_id: str) -> AgentAlert:
        return await self._resolve_alert(company_id, alert_id, "approve")

    async def reject_alert(self, company_id: str, alert_id: str) -> AgentAlert:
        return await self._resolve_alert(company_id, alert_id, "reject")

    async def _resolve_alert(self, company_id: str, alert_id: str, decision: str) -> AgentAlert:
        alert = await self.repo.get_alert(company_id, alert_id)
        if not alert:
            raise NotFoundError("AgentAlert", alert_id)
        if alert.status != "pending":
            raise BusinessError(f"This alert was already resolved (status: {alert.status})")
        await resume_proposal(alert, decision, self.session)
        resolved = await self.repo.get_alert(company_id, alert_id)
        assert resolved is not None
        return resolved

    async def drain_triggers(self, company_id: str) -> int:
        """Opportunistic, event-driven reaction: since the last drain, some
        business actions (a sale dropping stock below minimum, a purchase
        changing a cost) left breadcrumbs in pending_agent_triggers. Run only
        the agents those breadcrumbs point at, then mark them processed.

        Cheap no-op when the queue is empty (the common case), so it's safe
        to call on every Agentes page load — unlike the full daily sweep,
        this doesn't run all four detectors every time."""
        triggers = await self.repo.get_company_unprocessed_triggers(company_id)
        if not triggers:
            return 0
        agent_keys = {t.agent_key for t in triggers}
        started = await self.sweep_company(company_id, only_agents=agent_keys)
        # Mark processed regardless of per-candidate outcome: detectors
        # re-derive from live DB state and the daily sweep is the backstop,
        # so a breadcrumb that produced nothing shouldn't be retried on every
        # page load.
        await self.repo.mark_triggers_processed(triggers)
        return started

    async def sweep_company(self, company_id: str, only_agents: set[str] | None = None) -> int:
        """Runs each enabled agent's detector for one company and starts a
        proposal for each new candidate. Returns how many were started.
        `only_agents` limits the run to a subset (used by drain_triggers);
        None runs them all (the daily sweep)."""
        configs = {c.agent_key: c for c in await self.repo.get_configs(company_id)}
        pending = await self.repo.list_alerts(company_id, status="pending")
        # De-dup key per pending alert. Product agents key on product_id/sku;
        # Mara (and any non-product agent) sets an explicit dedup_key (the
        # entity id), so the key generalizes beyond products.
        def _dedup_key(args: dict) -> str | None:
            return args.get("dedup_key") or args.get("product_id") or args.get("sku")

        already_proposed = {
            f"{a.agent_key}:{_dedup_key(a.proposed_action.get('args', {}))}" for a in pending
        }

        started = 0
        errors: list[str] = []
        for agent_key, detect in DETECTORS.items():
            if only_agents is not None and agent_key not in only_agents:
                continue
            config = configs.get(agent_key)
            if config and not config.enabled:
                continue
            candidates = await detect(company_id, self.session)
            for candidate in candidates:
                key = f"{agent_key}:{candidate.get('dedup_key') or candidate.get('product_id')}"
                if key in already_proposed:
                    continue
                try:
                    await run_proposal(company_id, agent_key, candidate, self.session)
                    started += 1
                except Exception as exc:  # noqa: BLE001 — one bad candidate (e.g. LLM outage) shouldn't sink the sweep
                    await self.session.rollback()
                    errors.append(f"{key}: {exc}")
        if errors:
            print(f"[agents.sweep_company] {company_id}: {len(errors)} proposal(s) failed: {errors}")
        return started

    async def sweep_all_companies(self) -> dict[str, int]:
        results = {}
        for company_id in await self.repo.list_company_ids():
            try:
                results[company_id] = await self.sweep_company(company_id)
            except Exception as exc:  # noqa: BLE001 — one company's failure shouldn't block the rest
                await self.session.rollback()
                results[company_id] = -1
                print(f"[agents.sweep_all_companies] {company_id} failed entirely: {exc}")
        return results
