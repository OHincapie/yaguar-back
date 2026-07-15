"""Margin math, shared so every surface (Inventario display via ProductRead,
Dashboard KPIs, Kuri the margins agent) computes it the same way and honours
the company's configured basis.

Two conventions a distributor might think in:
- "price" basis (margen sobre el precio de venta): (price - cost) / price.
  The accounting-standard gross margin; always < 100%. "Qué % de lo que
  cobro es ganancia."
- "cost" basis (margen sobre el costo / markup): (price - cost) / cost.
  Can exceed 100%. "Cuánto le gano a lo que me costó." — often more
  intuitive for a small business owner.

Company.margin_basis picks which one the whole system shows. Default
"price" preserves the behavior everything had before this was configurable.
"""

from enum import StrEnum


class MarginBasis(StrEnum):
    PRICE = "price"
    COST = "cost"


# Kuri's flag/target thresholds, per basis — expressed in the same basis the
# user sees so an alert's "margen actual X%" matches the Inventario column.
# 15%/25% on price ≈ 18%/33% on cost; rounded to friendly numbers per basis.
LOW_MARGIN_THRESHOLD = {MarginBasis.PRICE: 0.15, MarginBasis.COST: 0.20}
TARGET_MARGIN = {MarginBasis.PRICE: 0.25, MarginBasis.COST: 0.40}


def normalize_basis(value: str | None) -> MarginBasis:
    return MarginBasis.COST if value == MarginBasis.COST else MarginBasis.PRICE


def margin_pct(price: float, cost: float, basis: MarginBasis) -> float:
    """Margin as a percentage (not a fraction), in the given basis. Returns
    0 when the denominator is 0 (no price, or no cost)."""
    if basis == MarginBasis.COST:
        return (price - cost) / cost * 100 if cost > 0 else 0.0
    return (price - cost) / price * 100 if price > 0 else 0.0


def price_for_target_margin(cost: float, target_fraction: float, basis: MarginBasis) -> float:
    """The selling price that yields `target_fraction` margin on `cost` in
    the given basis. Falls back to cost when it can't be computed."""
    if cost <= 0:
        return cost
    if basis == MarginBasis.COST:
        return round(cost * (1 + target_fraction), 2)
    if target_fraction >= 1:  # guard: price-basis margin can't reach 100%
        return round(cost, 2)
    return round(cost / (1 - target_fraction), 2)
