# Yaguar — Backend

Context for whoever (or whichever model) picks this up next. This is descriptive, not
prescriptive — nothing here is a hard rule, it's "how things are and why", so you can
change any of it once you understand the tradeoffs that led here. Written 2026-07-07.

## What this is

Yaguar is an ERP for small distributors/wholesalers (inventory, POS, purchases, sales,
ledger, customers, suppliers), with a differentiating feature: internal AI agents that
watch the business and propose actions a human must approve before anything executes.
See `docs/PRODUCT.md` in the frontend repo (local path `../Front/app/docs/`) for the
product vision — versioned there since 2026-07-10, along with DESIGN.md, backlog.md,
and MEJORAS.md (forward-looking improvement options).

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
`dashboard` (KPIs), `agents` (the AI agents — see below), `ai_usage` (token/usage log),
`chat` (copilot conversation persistence — see below).

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
`UserCompany` (role: owner/admin/member).

**Roles and per-module permissions (added 2026-07-07)**: `get_current_user` looks up
the caller's `UserCompany` row *fresh on every request* (not embedded in the JWT) to
get `role` and `modules` — a deliberate choice over the cheaper JWT-embedded approach,
so revoking a "member"'s access to a module takes effect immediately instead of on
their next login. `AuthContext.has_module(key)` is the check: owner/admin always pass;
"member" only passes if `key` is in their `modules` list (JSONB column on
`UserCompany`, keys defined in `accounts.models.MODULE_KEYS` — keep in sync with the
frontend's `nav` ids).

**Only mutating endpoints (POST/PUT/PATCH/DELETE) are gated by `require_module()`,
applied per-route, not per-router.** This was *not* the first design — the first pass
gated entire routers including GET, and broke immediately in testing: Inventario reads
Suppliers for names, Ventas/POS/Compras read Products, POS/Ventas/Dashboard read
Customers, Dashboard aggregates across everything. A "member" with only `inventario`
got a 403 crash loading Inventario itself. Any authenticated company member can now
**read** across the whole business (see each router file for the exact split — the
convention is `_require_<module> = Depends(require_module("<module>"))` declared once
near the top, then referenced in `dependencies=[...]` on each write route). `dashboard`
has no gate left at all — its one endpoint is a read-only KPI aggregate, and there's
nothing left to restrict once every domain's reads are open. `require_owner_or_admin`
is the separate, role-only (not module) check used for `/auth/users` (managing other
users) and `PUT /auth/settings` (company-wide config) — account-level actions, not tied
to a business module.

`POST /auth/users` creates a user directly with a password the admin sets (no email
invitation flow exists — there's no email-sending infrastructure in this app at all).
If the email already exists as a `User` in a *different* company, it reuses that user
and just adds a new `UserCompany` membership rather than erroring — a person can belong
to more than one company.

`CompanyUserUpdate.password` (added 2026-07-09) lets an owner/admin reset another
user's password directly through `PUT /auth/users/{id}` — the only account-recovery
path that exists, since there's no "forgot password" flow either. Because
`password_hash` lives on the shared `User` row, not per `UserCompany` membership,
resetting it from one company's Equipo screen changes that person's password
everywhere, including any other company they belong to — worth knowing if the
multi-company-membership case ever comes up in a support conversation.

**Forced password change (added 2026-07-09)**: `User.must_change_password` is set
`True` whenever someone *other* than the user picked their current password — on
creation via `POST /auth/users` (admin-set temp password) and on an admin reset via
`CompanyUserUpdate.password`. `POST /auth/register` (a user creating their own company)
leaves it `False`, since they chose their own password there. `GET /auth/me` returns
the flag; the frontend blocks its entire app behind a "set a new password" screen while
it's `True`. The only way to clear it is `POST /auth/change-password`
(`ChangePasswordRequest{current_password, new_password}`) — self-service, requires the
current password even though the caller is already authenticated via JWT (a leaked/
captured session token shouldn't be enough on its own to silently rotate someone's
password). This endpoint doubles as a normal "change my password" action too, not just
the forced flow — nothing gates it behind the flag being set.

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

`Sale.status` (pagado/pendiente) is derived automatically from the payment methods used
inside `SaleService._resolve_payments` — any credit method → pendiente, everything else
→ pagado immediately. This is the *only* place that decides it; `SaleCreate` has no
`status` field on purpose, so the POS checkout path, the manual "create sale" path, and
the chat's `create_sale` tool can't drift apart (POS and manual sales used to compute
this differently until it was unified).

Editing a sale's lines reverses the old lines' stock impact
(`InventoryService.reverse_sale`, mirrors `apply_sale` including kit expansion) before
reapplying the new ones.

## Split payments and configurable payment methods (added 2026-07-08)

Payment methods are a company-scoped table (`payment_methods`), not a hardcoded enum —
every company gets 4 defaults seeded (Efectivo/Tarjeta/Transferencia/Crédito, matching
the old enum's values) on registration (`AccountsService.register`), and can add more
(e.g. "Nequi") via `POST /payment-methods` (owner/admin only, mirrors
`require_owner_or_admin`). A **fully-free sale** (every line priced at 0, so total is 0 — e.g. a POS
gift) is allowed: `_resolve_payments` relaxes the "each amount must be
positive" rule to accept the single 0 amount when `total` rounds to 0, and
forces the sale to `pagado` (a free sale owes nothing, so credit rules
don't apply). Normal sales still require positive amounts. Stock is
deducted by qty in `apply_sale` regardless of price, so a $0 line still
comes off inventory — the POS exposes this via an editable per-line price.

`PaymentMethodConfig.is_credit` marks which ones mean "not
paid yet" rather than real money changing hands.

A sale can be paid across several methods at once — `SaleCreate.payments` is a
`list[PaymentLine]` (`payment_method_id` + `amount`), not one field, and a new
`sale_payments` table holds one row per method used. `SaleService._resolve_payments`
validates the set: amounts must sum to the sale's `total` (0.01 float tolerance), and
credit is **deliberately all-or-nothing** — a credit line can't be combined with any
other method in the same sale, and can't be used at all if the sale has no customer
(`customer_id is None`). This is *not* a partial-payment/accounts-receivable feature —
`Customer.saldo` isn't wired to anything real (see the Product kits section's sibling
gotcha list — actually see below: it's a dormant field, same as `ltv`/`orders`/
`due_date`), so there's nowhere for a partial credit balance to live. If that's ever
built, it's a separate, bigger feature.

`Sale.customer_id` is nullable — a walk-in/casual sale with no registered buyer. Turned
out the live DB column was already nullable despite the old SQLModel field claiming
otherwise (no `Optional[str]`), so no migration was needed for that part; only the
`payment_methods`/`sale_payments` tables were new. `Sale.payment_method` is now a
denormalized *display* string (e.g. `"Efectivo + Transferencia"`), recomputed from the
payment lines on every create/update — not the source of truth, just a convenience so
listing sales doesn't need a join every time.

**Dormant fields worth knowing about, so nobody's surprised nothing reacts to them**:
`Customer.saldo`/`ltv`/`orders` and `Sale.due_date` are all columns that exist in the
schema but that no business logic reads or writes anywhere — they're either seed data
or reserved for a not-yet-built feature (accounts receivable, Mara the collections
agent). Don't assume changing a sale's payment status will move `Customer.saldo`; it
won't, nothing currently touches it.

## Cartera / accounts receivable (added 2026-07-13)

Credit sales are finally tracked to collection. `sale_abonos` holds partial
payments registered after the fact — deliberately separate from
`sale_payments`, whose rows describe how the sale was *arranged* at creation
and must sum exactly to `Sale.total`; abonos accumulate until they cover it
(`SaleService.register_abono` flips the sale to `pagado` then).
`POST /sales/{code}/abonos` validates: open sale (pendiente/vencido), a real
non-credit active method, positive amount, can't exceed the outstanding
balance. `GET /sales/cartera` returns every open credit sale with customer
name, due date, abonado, saldo, and `overdue` computed **at read time** from
`due_date` — nothing persists a "vencido" status, so the view doesn't depend
on the daily cron. (Route declared before `/{code}` so "cartera" isn't
parsed as a sale code.)

`Company.credit_days` (default 30) sets a credit sale's `due_date` at
creation (`SaleCreate.due_date` overrides). `Customer.saldo` is now real and
kept in sync incrementally: +total on credit sale creation, -amount per
abono, and a before/after-contribution delta on line edits, payment
replacement, manual status flips, and deletion (clamped at 0 so legacy seed
values can't go negative — `_adjust_saldo`). Replacing payment lines on a
sale that already has abonos is rejected outright. The ledger still
recognizes income at sale creation (flat-book behavior, unchanged) — the
receivable side lives on `Customer.saldo`, abonos write no ledger entries.
Migration `0011_cartera` also backfilled `due_date` on open sales and
recomputed every `customers.saldo` from real open sales.

## Purchases: cost sync, editing, deletion

Receiving a purchase order (`POST /purchases/{code}/receive`) syncs the product's
`cost` to the received line's `unit_cost` whenever they differ — a supplier's price
change becomes the new cost of record. It also drops a row in `pending_agent_triggers`
for the (not-yet-built) margins agent. Purchases reject any line targeting a bundle
product at creation time.

`PUT /purchases/{code}` (edit notes/lines, recalculates `total`) and
`DELETE /purchases/{code}` (added 2026-07-09) are both blocked once a purchase is
`recibido` — that's the *only* status with a real-world effect (stock added, ledger
entry written by `receive()`). A `cancelado` purchase never went through `receive()`,
so editing/deleting it is still allowed — it never touched real data, no different from
a `borrador` for this purpose. `SaleService.delete_sale` has no such status gate: unlike
a purchase, a sale's inventory effect happens immediately at creation (`apply_sale`
inside `create_sale`) regardless of `pagado`/`pendiente`, so there's no "safe,
not-yet-applied" state to check — deleting a sale always reverses its lines via
`InventoryService.reverse_sale` (the same helper editing a sale's lines already uses)
and removes the linked ledger entry.

## The AI agents (`src/domains/agents/`)

Five agents watch the business and propose actions a human approves: Yaco
(compras, predictive reorder), Mara (cobros, overdue credit), Inti (stock,
quiebre/baja rotación), Kuri (precios, márgenes) and Khipu (catalogo, data
audit — added 2026-07-17). All five have real detectors wired in
`AgentService.DETECTORS`.

**Engine**: LangGraph, checkpointed to the same Neon Postgres via `AsyncPostgresSaver`
(needs `psycopg[binary]`, not plain `psycopg` — Vercel's Python runtime has no system
`libpq`, discovered the hard way).

- `detectors.py` — pure Python, no LLM, with ONE deliberate exception. Computes
  facts deterministically (stock below minimum, no sales in 30 days, suggested
  reorder qty/price). Trusted arithmetic. **The exception is Khipu**
  (`detect_catalog_issues`): "a cellphone filed under Audífonos" is a language
  judgment, not arithmetic, so its detector asks an LLM to *suspect*
  misassignments from the real category list + catalog, then validates every
  suspicion in Python before it becomes a candidate — real SKU, suggested
  category must exist verbatim in the company's list (the LLM can never invent
  one), confidence ≥ 70, cap of 20 findings/sweep. Its action
  (`update_product_category`) is never auto-applied; a human confirms every
  recategorization. Verified live in prod on day one: it caught a real
  "COLLAGEN" product filed under "Bebé" and proposed "Naturistas" (95%).
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

## Chat persistence + audit (`src/domains/chat/`, added 2026-07-16)

Persists the "Inicio" copilot conversations (which used to live only in the browser).
`chat_conversations` (company + user scoped, title derived from the first user message)
and `chat_messages` (one row per UIMessage, PK = the client-generated message id, `parts`
stored verbatim as JSONB — text, tool calls, approvals, and attachments inline as base64).
The frontend's chat route calls `PUT /chat/conversations/{id}/sync` server-side on every
finished turn with the full message list; `ChatService.sync_conversation` **upserts by
message id** (idempotent — re-sending the whole conversation each turn just updates
existing rows and inserts new ones; a tool continuation updates its assistant row in
place). Ownership is enforced on the client-supplied conversation id: writing to another
user's/company's conversation is a `ForbiddenError`, reading one is a 404 (no existence
leak).

`GET /chat/conversations` + `/{id}` are the user's own history (scoped to the caller).
**Cross-company audit is a separate, superadmin-only surface**: `User.is_superadmin` (a
platform-operator flag, deliberately *not* a company role in `UserCompany` — it crosses
the multi-tenant boundary, so it lives on the shared `User` and is only ever set by hand
in the DB, never via any endpoint). `AuthContext.is_superadmin` is looked up fresh per
request (same as role/modules, so revoking takes effect immediately), gated by
`require_superadmin`. The `chat_audit_router` (`/chat/audit/conversations[/{id}]`) is the
only thing behind it — no in-app screen yet, queried directly by the operator. Everything
here was verified live in prod (persist a real turn → own history → audit 403 for a
normal user, 200 with company/user/message_count once superadmin) before shipping.

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
