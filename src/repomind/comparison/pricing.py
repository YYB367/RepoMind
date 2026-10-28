"""Optional, explicit price-card estimates. Actual billing is never inferred."""

from datetime import date
from decimal import Decimal, DecimalException
import hashlib
import json
import math
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, StringConstraints, model_validator

from repomind.domain.models import Contract, Text
from repomind.memory.store import _unique_keys

Money = Annotated[Decimal, Field(ge=0, allow_inf_nan=False)]


class ModelRate(Contract):
    input_per_million: Money
    output_per_million: Money
    cached_input_per_million: Money | None = None
    valid_from: date
    valid_until: date | None = None
    source: Text

    @model_validator(mode="after")
    def valid_interval(self):
        if self.valid_until is not None and self.valid_until < self.valid_from:
            raise ValueError("pricing valid_until precedes valid_from")
        return self


class PriceCard(Contract):
    schema_version: Literal["1"] = "1"
    currency: Annotated[str, StringConstraints(pattern=r"^[A-Z]{3}$")]
    models: dict[str, ModelRate]


def load_price_card(path: str | Path) -> tuple[PriceCard, str]:
    data = Path(path).read_bytes()
    card = PriceCard.model_validate(json.loads(data.decode("utf-8-sig"), object_pairs_hook=_unique_keys))
    return card, hashlib.sha256(data).hexdigest()


def estimate_cost(usage: dict, model: str | None, card: PriceCard | None, *,
                  live: bool, run_date: date, operation: str = "embedding", usage_complete: bool | None = None) -> dict:
    result = {"amount": None, "currency": card.currency if card else None, "model": model,
              "is_estimate": True, "actual_billing_verified": False}
    if not live:
        return {**result, "status": "not_measured_recorded_vectors"}
    if usage_complete is False:
        return {**result, "status": "usage_not_proven_complete"}
    if operation not in {"embedding", "chat", "generation"}:
        return {**result, "status": "unsupported_operation"}
    if card is None:
        return {**result, "status": "no_price_card"}
    if model not in card.models:
        return {**result, "status": "model_rate_missing"}
    rate = card.models[model]
    if run_date < rate.valid_from or (rate.valid_until is not None and run_date > rate.valid_until):
        return {**result, "status": "rate_not_valid_on_run_date"}

    def tokens(*names):
        values = [usage[name] for name in names if name in usage]
        if not values or any(type(value) is not int or value < 0 for value in values):
            return None
        return values[0] if len(set(values)) == 1 else None

    inputs = tokens("prompt_tokens", "input_tokens")
    outputs = 0 if operation == "embedding" else tokens("completion_tokens", "output_tokens")
    if inputs is None or outputs is None:
        return {**result, "status": "usage_incomplete_or_ambiguous"}
    cached = 0
    if rate.cached_input_per_million is not None and rate.cached_input_per_million != rate.input_per_million:
        cached = tokens("cached_input_tokens")
        if cached is None or cached > inputs:
            return {**result, "status": "cache_token_split_missing"}
    try:
        amount = (Decimal(inputs-cached)*rate.input_per_million + Decimal(outputs)*rate.output_per_million
                  + Decimal(cached)*(rate.cached_input_per_million if rate.cached_input_per_million is not None
                                     else rate.input_per_million))/Decimal(1_000_000)
        numeric = float(amount)
    except (DecimalException, OverflowError, ValueError):
        return {**result, "status": "estimate_out_of_numeric_range"}
    if not math.isfinite(numeric) or (amount != 0 and numeric == 0):
        return {**result, "status": "estimate_out_of_numeric_range"}
    return {**result, "amount": numeric, "amount_decimal": str(amount), "status": "estimated_from_explicit_card",
            "usage_basis": {"input_tokens": inputs, "cached_input_tokens": cached, "output_tokens": outputs},
            "price_source": rate.source, "valid_from": rate.valid_from.isoformat()}
