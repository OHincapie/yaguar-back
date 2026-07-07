# Yaguar — Backend

Context for whoever (or whichever model) picks this up next. This is descriptive, not
prescriptive — nothing here is a hard rule, it's "how things are and why", so you can
change any of it once you understand the tradeoffs that led here. Written 2026-07-07.

## What this is

Yaguar is an ERP for small distributors/wholesalers (inventory, POS, purchases, sales,
ledger, customers, suppliers), with a differentiating feature: internal AI agents that
watch the business and propose actions a human must approve before anything executes.
See `Front/PRODUCT.md` (in the frontend repo, not versioned here) for the product vision.

This repo is the API. The frontend (Next.js) lives in a sibling repo, `yaguar-front`
(local path `../Front/app`), deployed separately.

- **Stack**: FastAPI + SQLModel (async, `asyncpg`), Neon Postgres, Alembic, JWT auth,
  deployed on Vercel (serverless Python).
- **Demo login**: `admin@yaguar.demo` / `admin123`, company "Yaguar Demo". Seeded via
  `src/seed.py`.
- **Production URL**: `https://yaguar-back.vercel.app`, API prefix `/api`.

## Architecture

Domain-driven, one folder per domain under `src/domains/<domain>/`:

```
models.py      SQLModel table classes
schemas.py     Pydantic request/response shapes (Create/Update/Read)
repository.py  DB access — every method takes company_id first
service.py     Business logic, orchestrates repositories
router.py      FastAPI routes, thin — delegates to service
```

Domains: `accounts` (companies/users/auth/settings), `products` (+ categories + kits),
`inventory`, `suppliers`, `customers`, `sales`, `purchases`, `ledger`, `pos` (checkout),
`dashboard` (KPIs), `agents` (the AI agents — see below).

`src/app.py` wires all routers under `/api`. `src/shared/` has cross-cutting stuff:
`database.py` (engine + session), `settings.py` (env config), `middleware/auth.py`
(JWT decode → `CurrentUser` dependency carrying `user_id` + `company_id`),
`middleware/errors.py` (typed exceptions → HTTP status mapping: `NotFoundError`→404,
`ConflictError`→409, `BusinessError`→422, `UnauthorizedError`→401).

## Multi-tenancy

Shared database, **app-layer** isolation — every repository method takes `company_id`
and filters by it explicitly. This was a conscious choice over Postgres Row-Level
Security: simpler to reason about and debug, at the cost that a missed `company_id`
filter in a new query is a real data-leak risk with no DB-level safety net. If this ever
needs hardening, RLS is the natural next layer, not a rewrite.

Entities with a human-facing code (`Product.sku`, `Customer.code`, `Supplier.code`,
`Sale.code`, `Purchase.code`, `Category.code`) use a **UUID surrogate primary key** +
the code as a plain column with `UniqueConstraint(company_id, code)`. The code is only
unique *within* a company — two companies can both have SKU `TEC-1180`. Don't use the
human code as a foreign key anywhere; always the UUID `id`.

Company-level settings (currently: POS discount/tax on/off + percentage) live directly
on the `Company` model (`accounts/models.py`) rather than a separate settings table —
fine at this size, revisit if the settings list grows a lot.

## Auth

JWT in an `Authorization: Bearer` header, claims `sub` (user_id) and `cid` (company_id).
`CurrentUser = Annotated[AuthContext, Depends(get_current_user)]` is the dependency
every protected route uses. Switching companies (`POST /auth/switch-company`) just
issues a new token with a different `cid` — a user can belong to multiple companies via
`UserCompany` (role: owner/admin/member), but **roles aren't enforced anywhere yet** —
any authenticated member can do anything in their current company.

## Product kits/bundles

A product can be `is_bundle=True`, composed of N units of one or more *base* (non-bundle)
products via `product_components`. A kit has no `InventoryLevel` row of its own — its
stock is derived at read time (`InventoryService._derive_bundle_level`): the minimum
across components of `floor(component_stock / component_qty)`. Selling a kit deducts
from its components (`InventoryService.apply_sale`'s bundle branch), not itself.
Purchases and manual stock adjustments reject bundles outright — you buy/adjust the
components, never the kit. Kits can't contain other kits (no recursion) — a deliberate
simplification, not a limitation anyone's hit yet.

## Sales: discount/tax and status

`Sale` stores `subtotal`, `discount_amount`, `tax_amount`, `total` — all computed once
at creation time from the company's *current* `discount_pct`/`tax_pct`/`*_enabled`
settings (`SaleService._compute_amounts`) and then frozen, so a sale's numbers don't
drift if the company later changes its settings. Editing a sale's lines
(`PUT /sales/{code}`) recomputes all four and also patches the linked ledger entry's
credit so accounting doesn't go stale.

`Sale.status` (pagado/pendiente) is derived automatically from `payment_method` inside
`SaleService.create_sale` — Crédito → pendiente, everything else → pagado immediately.
This is the *only* place that decides it; `SaleCreate` has no `status` field on purpose,
so the POS checkout path and the manual "create sale" path can't drift apart (they used
to — POS auto-computed it, manual sales always defaulted to pendiente until this was
unified).

Editing a sale's lines reverses the old lines' stock impact
(`InventoryService.reverse_sale`, mirrors `apply_sale` including kit expansion) before
reapplying the new ones.

## Purchases: cost sync

Receiving a purchase order (`POST /purchases/{code}/receive`) syncs the product's
`cost` to the received line's `unit_cost` whenever they differ — a supplier's price
change becomes the new cost of record. It also drops a row in `pending_agent_triggers`
for the (not-yet-built) margins agent. Purchases reject any line targeting a bundle
product at creation time.

## The AI agents (`src/domains/agents/`)

Four planned agents — Yaco (compras), Mara (cobranzas), Inti (inventario), Kuri
(márgenes) — that watch the business and propose actions a human approves. **Only Inti
has a real detector right now**; the other three exist as config rows (roster entries
in the frontend) with nothing behind them.

**Engine**: LangGraph, checkpointed to the same Neon Postgres via `AsyncPostgresSaver`
(needs `psycopg[binary]`, not plain `psycopg` — Vercel's Python runtime has no system
`libpq`, discovered the hard way).

- `detectors.py` — pure Python, no LLM. Computes facts deterministically (stock below
  minimum, no sales in 30 days, suggested reorder qty/price). Trusted arithmetic.
- `graph.py` — the shared graph every agent runs. **Read this before adding a new
  agent's node logic**: `compose` (LLM turns facts into title/body via structured
  output) → `persist` (writes the `AgentAlert` row, decides auto-apply vs. ask) →
  `gate` (calls `interrupt()`, *only* if not auto-applying) → `execute` (dispatches to
  `actions.py`). The LLM never invents numbers or calls write tools directly — it only
  writes the human-readable message, using facts we hand it.
- **A real gotcha already hit and fixed**: LangGraph re-runs a node from the top when
  resuming past an `interrupt()` inside it. `persist` and `gate` are separate nodes
  *because of this* — putting the alert-creation write and the `interrupt()` call in
  the same node duplicated the alert on every approve/reject (the interrupt scope
  resumes by re-executing the whole node, including the write before the pause).
  Whatever you add here: never put a DB write before an `interrupt()` in the same node.
- `actions.py` — small registry (`create_purchase`, `update_product_price`) the human's
  approval dispatches into. Add an entry here + a case in `build_proposal()` for a new
  agent's write action.
- `llm.py` — the only file that should import a provider SDK. `get_chat_model()` reads
  `LLM_PROVIDER`/`LLM_MODEL` from settings; swapping providers is an env var change.
  Currently OpenAI (`gpt-5-mini`) — was Gemini until billing was set up on OpenAI;
  Gemini's free tier (~20 req/day/model) is too rate-limited for anything beyond
  testing. If you add a provider branch here, keep the lazy import pattern (only import
  the SDK actually configured, so an unconfigured provider's missing package doesn't
  break startup).

**Trigger**: `GET /api/agents/sweep-all` behind Vercel's automatic `CRON_SECRET` →
`Authorization: Bearer` convention (not a custom header — that's a platform convention,
not ours). Wired to run daily in `vercel.json` (Hobby plan only allows daily cron;
tighten the schedule if the plan changes). `POST /api/agents/sweep` is the per-company
manual trigger the frontend's "Revisar ahora" button calls.

`pending_agent_triggers` exists in the schema (a lightweight event queue — a business
action can drop a breadcrumb instead of waiting on an LLM call mid-request) but
**nothing consumes it yet** — only the periodic full sweep runs detection today. The
purchase-receive cost-sync is the one place that already writes to it (for the
not-yet-built margins agent).

Adding a new agent = a detector function + a system prompt entry in
`prompts.AGENT_SYSTEM_PROMPTS` + a case in `graph.build_proposal()`/`actions.py`. The
graph structure itself (`_build_graph`) shouldn't need to change.

## Known gotchas (things that broke before, worth not re-breaking)

- **`sqlmodel.select` vs `sqlalchemy.select`** — always import `select` from `sqlmodel`
  in repositories. The sqlalchemy one makes `session.exec()` return raw Row tuples
  instead of model instances.
- **Enum columns**: SQLModel's default column type for a `StrEnum` field expects the
  DB to store the enum's *name*, not its *value*. This app's enums store values (e.g.
  `"Mayorista"`, not `"MAYORISTA"`) in plain varchar columns, so every enum `Field()`
  needs `sa_type=AutoString` (from `sqlmodel`) explicitly.
- **Datetime columns**: need `sa_type=DateTime(timezone=True)` (from `sqlalchemy`) or
  asyncpg parameter binding fails comparing offset-naive vs. offset-aware datetimes.
- **`expire_on_commit=False`** is set on the engine (`shared/database.py`) because
  several handlers (POS checkout, purchase receive) commit more than once per request;
  the default expire-on-commit behavior causes `MissingGreenlet` when FastAPI tries to
  serialize an attribute that would need a lazy re-fetch outside an awaited context.
- **Reading an attribute after `session.rollback()`** hits the same `MissingGreenlet`
  failure mode — rollback expires every attribute on objects in the session, so a
  lazy-reload gets attempted outside a valid async/greenlet context. If you catch an
  `IntegrityError`, read whatever you need for the error message *before* rolling back
  (see the delete methods in `products`/`customers`/`suppliers` repositories for the
  pattern — this exact bug shipped once already).
- **JSON columns**: use `sqlalchemy.dialects.postgresql.JSONB` explicitly, not
  SQLModel's generic `JSON`, when the actual Postgres column is `jsonb` — asyncpg needs
  the right type on the SQLAlchemy side to bind parameters with the correct cast.
- **Deleting a row with FK references** (e.g. a product with inventory/sale history)
  needs `try/except IntegrityError` around the commit, translated to `ConflictError` —
  otherwise Postgres's raw FK violation propagates as an unhandled 500. Only
  products/customers/suppliers have this today; the same gap likely exists anywhere
  else with a `delete()` method that doesn't wrap the commit.

## Migrations

Alembic migrations exist under `alembic/versions/` (`0001` through `0006`), but in
practice most schema changes this project has made were **applied directly against
Neon via the Neon MCP tools** (`mcp__Neon__run_sql`) during the session, then written
up as an Alembic migration file afterward purely for history/documentation — not run
through `alembic upgrade` against the live DB. If you add a migration file, also
`UPDATE alembic_version SET version_num = '...'` directly if you're applying the schema
change by hand the same way. Migration `0003`'s `downgrade()` raises
`NotImplementedError` — the multi-tenant migration was never meant to be reversible.

## Testing

No automated test suite exists (`tests/` referenced in `pyproject.toml`'s dev deps but
empty/absent) despite real business logic now running (kits, multi-tenant isolation,
checkout, agent approval flow). Everything so far has been verified with `curl` against
the live production deployment plus direct Neon queries for setup/cleanup — see any
recent commit message in this repo's history for the pattern (create test data via the
real API, verify, clean up via Neon MCP afterward). Worth building real tests before
this gets much bigger.

## Deployment

`vercel deploy --prod --yes` from this directory. Two separate Vercel projects exist
for backend and frontend — don't confuse them. Env vars are managed via
`vercel env add/rm <NAME> production` (see `.env` locally for the current full list —
not committed, obviously). CORS is locked to `cors_allowed_origins` +
`cors_allowed_origin_regex` in `shared/settings.py` (matches `yaguar-front*.vercel.app`
for preview deployments), not a wildcard.
