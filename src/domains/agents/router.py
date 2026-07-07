from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.agents.repository import AgentRepository
from src.domains.agents.schemas import AgentAlertRead, AgentConfigRead, AgentConfigUpdate
from src.domains.agents.service import AgentService
from src.shared.database import get_session
from src.shared.middleware.auth import CurrentUser, require_module
from src.shared.settings import settings

router = APIRouter(prefix="/agents", tags=["agents"])
# Not applied at router level like every other domain: /sweep-all doesn't
# use CurrentUser at all (the cron hits it with CRON_SECRET, no logged-in
# user), so it's set per-endpoint here instead.
_require_agentes = Depends(require_module("agentes"))


def get_service(session: Annotated[AsyncSession, Depends(get_session)]) -> AgentService:
    return AgentService(AgentRepository(session), session)


@router.get("/configs", response_model=list[AgentConfigRead])
async def list_configs(current_user: CurrentUser, service: Annotated[AgentService, Depends(get_service)]):
    return await service.list_configs(current_user.company_id)


@router.put("/configs/{agent_key}", response_model=AgentConfigRead, dependencies=[_require_agentes])
async def update_config(
    current_user: CurrentUser,
    agent_key: str,
    data: AgentConfigUpdate,
    service: Annotated[AgentService, Depends(get_service)],
):
    return await service.update_config(current_user.company_id, agent_key, data)


@router.get("/alerts", response_model=list[AgentAlertRead])
async def list_alerts(
    current_user: CurrentUser,
    service: Annotated[AgentService, Depends(get_service)],
    status: str | None = None,
):
    return await service.list_alerts(current_user.company_id, status)


@router.post("/alerts/{alert_id}/approve", response_model=AgentAlertRead, dependencies=[_require_agentes])
async def approve_alert(current_user: CurrentUser, alert_id: str, service: Annotated[AgentService, Depends(get_service)]):
    return await service.approve_alert(current_user.company_id, alert_id)


@router.post("/alerts/{alert_id}/reject", response_model=AgentAlertRead, dependencies=[_require_agentes])
async def reject_alert(current_user: CurrentUser, alert_id: str, service: Annotated[AgentService, Depends(get_service)]):
    return await service.reject_alert(current_user.company_id, alert_id)


@router.post("/sweep", dependencies=[_require_agentes])
async def sweep(current_user: CurrentUser, service: Annotated[AgentService, Depends(get_service)]):
    """Manual trigger for the logged-in company — handy for testing
    without waiting for the cron. The cron itself uses /sweep-all."""
    started = await service.sweep_company(current_user.company_id)
    return {"proposals_started": started}


@router.get("/sweep-all")
async def sweep_all(
    session: Annotated[AsyncSession, Depends(get_session)],
    authorization: Annotated[str | None, Header()] = None,
):
    """Hit by the Vercel Cron job on a schedule, across every company. Not
    behind CurrentUser since there's no logged-in user — Vercel sends the
    CRON_SECRET env var as `Authorization: Bearer <secret>` automatically."""
    if authorization != f"Bearer {settings.cron_secret}":
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    service = AgentService(AgentRepository(session), session)
    return await service.sweep_all_companies()
