"""The generic proposal graph shared by every agent: turn one detected
candidate into a human-readable proposal, persist it, pause for approval
(unless autonomy rules allow skipping that), then execute or discard it.

Adding a new agent (Yaco, Mara, Kuri) means adding a detector + a prompt
+ entries in build_proposal()/actions.py — not touching this file.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlmodel.ext.asyncio.session import AsyncSession

from src.domains.agents.actions import execute_action
from src.domains.agents.llm import get_chat_model
from src.domains.agents.models import AgentAlert
from src.domains.agents.prompts import AGENT_SYSTEM_PROMPTS, AlertDraft
from src.domains.agents.repository import AgentRepository
from src.shared.settings import settings


class AgentState(TypedDict):
    company_id: str
    agent_key: str
    thread_id: str
    candidate: dict[str, Any]
    proposal: dict[str, Any] | None
    alert_id: str | None
    decision: str | None


def _checkpointer_conn_string() -> str:
    # AsyncPostgresSaver uses psycopg, not asyncpg — same Neon database,
    # different driver scheme than the rest of the app's SQLAlchemy URL.
    dsn = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return dsn if "sslmode=" in dsn else dsn + ("&" if "?" in dsn else "?") + "sslmode=require"


@asynccontextmanager
async def get_checkpointer():
    from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

    async with AsyncPostgresSaver.from_conn_string(_checkpointer_conn_string()) as checkpointer:
        yield checkpointer


def build_proposal(candidate: dict[str, Any], draft: AlertDraft) -> dict[str, Any]:
    if candidate["type"] == "quiebre":
        action = {
            "name": "create_purchase",
            "args": {
                "supplier_id": candidate["supplier_id"],
                "product_id": candidate["product_id"],
                "qty": candidate["suggested_qty"],
                "unit_cost": candidate["unit_cost"],
            },
        }
        auto_amount = candidate["total_cost"]
        context = [
            {"k": "Stock actual", "v": f"{candidate['stock_qty']:g} und"},
            {"k": "Punto mínimo", "v": f"{candidate['min_stock']:g} und"},
            {"k": "Sugerido", "v": f"{candidate['suggested_qty']:g} und"},
            {"k": "Costo OC", "v": f"${candidate['total_cost']:,.2f}"},
        ]
    elif candidate["type"] == "baja_rotacion":
        action = {
            "name": "update_product_price",
            "args": {"sku": candidate["sku"], "new_price": candidate["suggested_price"]},
        }
        # A price change is never auto-applied regardless of the autonomy
        # config — "auto_limit" is defined as a $ ceiling on purchase
        # orders for this agent, it has no meaning for pricing.
        auto_amount = None
        days = candidate["days_since_last_sale"]
        context = [
            {"k": "Sin venta", "v": f"{days} días" if days is not None else "nunca"},
            {"k": "Capital", "v": f"${candidate['stock_value']:,.2f}"},
            {"k": "Precio actual", "v": f"${candidate['current_price']:,.2f}"},
            {"k": "Precio sugerido", "v": f"${candidate['suggested_price']:,.2f}"},
        ]
    else:
        raise ValueError(f"Unknown candidate type: {candidate['type']!r}")

    return {"title": draft.title, "body": draft.body, "context": context, "action": action, "auto_amount": auto_amount}


def _build_graph(session: AsyncSession, checkpointer):
    repo = AgentRepository(session)

    async def compose(state: AgentState) -> dict[str, Any]:
        candidate = state["candidate"]
        model = get_chat_model().with_structured_output(AlertDraft)
        system = AGENT_SYSTEM_PROMPTS[state["agent_key"]]
        draft: AlertDraft = await model.ainvoke(
            [
                ("system", system),
                ("human", f"Datos de la situación detectada (ya calculados, no los inventes): {candidate}"),
            ]
        )
        return {"proposal": build_proposal(candidate, draft)}

    async def gate(state: AgentState) -> dict[str, Any]:
        proposal = state["proposal"]
        assert proposal is not None

        config = await repo.get_config(state["company_id"], state["agent_key"])
        auto_amount = proposal["auto_amount"]
        can_auto = config.enabled and config.autonomy == "auto" and auto_amount is not None and auto_amount <= (config.auto_limit or 0)

        alert = AgentAlert(
            company_id=state["company_id"],
            agent_key=state["agent_key"],
            title=proposal["title"],
            body=proposal["body"],
            context=proposal["context"],
            proposed_action=proposal["action"],
            status="auto_applied" if can_auto else "pending",
            thread_id=state["thread_id"],
        )
        alert = await repo.create_alert(alert)

        if can_auto:
            return {"alert_id": alert.id, "decision": "approve"}

        decision = interrupt({"alert_id": alert.id})
        return {"alert_id": alert.id, "decision": decision}

    async def execute(state: AgentState) -> dict[str, Any]:
        alert = await repo.get_alert(state["company_id"], state["alert_id"])  # type: ignore[arg-type]
        assert alert is not None
        now = datetime.now(timezone.utc)

        if state["decision"] != "approve":
            alert.status = "rejected"
            alert.resolved_at = now
            await repo.update_alert(alert)
            return {}

        try:
            result = await execute_action(state["company_id"], alert.proposed_action, session)
            alert.status = "auto_applied" if alert.status == "auto_applied" else "approved"
            alert.result = result
        except Exception as exc:  # noqa: BLE001 — surfaced to the user via the alert, not raised
            alert.status = "failed"
            alert.result = {"error": str(exc)}
        alert.resolved_at = now
        await repo.update_alert(alert)
        return {}

    graph = StateGraph(AgentState)
    graph.add_node("compose", compose)
    graph.add_node("gate", gate)
    graph.add_node("execute", execute)
    graph.add_edge(START, "compose")
    graph.add_edge("compose", "gate")
    graph.add_edge("gate", "execute")
    graph.add_edge("execute", END)
    return graph.compile(checkpointer=checkpointer)


async def run_proposal(company_id: str, agent_key: str, candidate: dict[str, Any], session: AsyncSession) -> None:
    """Kick off a new proposal for one detected candidate. Runs to
    completion if autonomy allows auto-apply, otherwise pauses at gate()
    with the AgentAlert already persisted as 'pending'."""
    import uuid

    thread_id = str(uuid.uuid4())
    async with get_checkpointer() as checkpointer:
        graph = _build_graph(session, checkpointer)
        await graph.ainvoke(
            {
                "company_id": company_id,
                "agent_key": agent_key,
                "thread_id": thread_id,
                "candidate": candidate,
                "proposal": None,
                "alert_id": None,
                "decision": None,
            },
            config={"configurable": {"thread_id": thread_id}},
        )


async def resume_proposal(alert: AgentAlert, decision: str, session: AsyncSession) -> None:
    async with get_checkpointer() as checkpointer:
        graph = _build_graph(session, checkpointer)
        await graph.ainvoke(Command(resume=decision), config={"configurable": {"thread_id": alert.thread_id}})
