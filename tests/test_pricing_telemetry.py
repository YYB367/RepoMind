from datetime import date
from datetime import datetime
from contextlib import contextmanager
import json
from types import SimpleNamespace

import pytest

from repomind.comparison.pricing import PriceCard, estimate_cost
from repomind.comparison.telemetry import MeasuredEmbedder
from repomind.intelligence.providers import OpenAICompatibleProvider, ProviderConfig
from repomind.intelligence.dashscope import DashScopeEmbeddingProvider


def card(**changes):
    rate = dict(input_per_million="2", output_per_million="4", valid_from="2026-01-01", source="synthetic test rates")
    rate.update(changes)
    return PriceCard(currency="USD", models={"test-model": rate})


def estimate(usage, rates=None, **options):
    return estimate_cost(usage, "test-model", rates, live=options.pop("live", True),
                         run_date=date(2026,10,27), **options)


def test_missing_prices_and_replayed_vectors_never_become_free_model_claims():
    assert estimate({"prompt_tokens": 100})["amount"] is None
    assert estimate({"prompt_tokens": 100}, card(), live=False)["status"] == "not_measured_recorded_vectors"


def test_explicit_rate_uses_actual_tokens_and_keeps_currency():
    result = estimate({"prompt_tokens": 250_000}, card())
    assert result["amount"] == .5 and result["currency"] == "USD"
    assert result["usage_basis"]["output_tokens"] == 0
    assert not result["actual_billing_verified"]


def test_zero_cached_price_is_respected_and_missing_cache_split_is_unknown():
    rates=card(cached_input_per_million="0")
    assert estimate({"prompt_tokens":100},rates)["status"] == "cache_token_split_missing"
    assert estimate({"prompt_tokens":100,"cached_input_tokens":100},rates)["amount"] == 0


@pytest.mark.parametrize("usage", [{}, {"prompt_tokens": True}, {"input_tokens":-1},
                                   {"prompt_tokens":10,"input_tokens":11}])
def test_incomplete_or_ambiguous_usage_is_not_invented(usage):
    assert estimate(usage,card())["amount"] is None


def test_expired_prices_and_missing_model_are_not_used():
    assert estimate({"input_tokens":100},card(valid_until="2026-02-01"))["amount"] is None
    assert estimate_cost({"input_tokens":100},"different-model",card(),live=True,run_date=date(2026,10,27))["amount"] is None


def test_measured_wrapper_tracks_true_request_delta_and_byte_hashes():
    class Provider:
        name="fake"
        fingerprint="fp"
        request_count=0
        usage={}
        config=SimpleNamespace(embedding_dimensions=2)
        def embed(self,texts):
            self.request_count+=1
            self.usage={"prompt_tokens":10,"total_tokens":10}
            return [[1,0] for _ in texts]
    measured=MeasuredEmbedder(Provider(),live=True)
    assert measured.dimension==2
    assert measured.embed(["database"])==[[1.,0.]]
    call=measured.calls[0]
    assert call["remote_request_delta"]==1 and call["usage_delta"]["prompt_tokens"]==10
    assert len(call["input_hashes"][0])==64 and call["error_type"] is None


def test_invalid_return_records_failure_without_masking_original_error():
    class Provider:
        fingerprint="fp"
        def embed(self,texts): return [[float("nan")]]
    measured=MeasuredEmbedder(Provider(),live=False)
    with pytest.raises(ValueError): measured.embed(["text"])
    assert measured.calls[0]["vector_hashes"] is None
    assert measured.calls[0]["error_type"]


class Responses:
    """An in-process HTTP peer; no socket, actual account, or .env is used."""
    def __init__(self, replies):
        self.replies = list(replies)

    @contextmanager
    def open(self, request, timeout):
        encoded = json.dumps(self.replies.pop(0)).encode()
        yield SimpleNamespace(status=200, headers={"Content-Length": str(len(encoded))}, read=lambda size: encoded[:size])


def metered_openai(replies):
    provider = OpenAICompatibleProvider(ProviderConfig(base_url="https://synthetic.invalid", api_key="not-a-real-key", embedding_model="test-model"))
    provider._opener = Responses(replies)
    return MeasuredEmbedder(provider, live=True)


def vector_reply(usage=None):
    result = {"data": [{"index": 0, "embedding": [1.0, 0.0]}]}
    if usage is not None:
        result["usage"] = usage
    return result


def test_missing_usage_after_success_is_unknown_and_not_a_zero_token_call():
    measured = metered_openai([vector_reply({"prompt_tokens": 12}), vector_reply()])
    measured.embed(["first"])
    assert measured.calls[0]["usage_complete"]
    measured.embed_query("second")
    assert measured.usage == {"prompt_tokens": 12}
    assert measured.usage_report_counts == {"prompt_tokens": 1}
    assert measured.calls[1]["usage_delta"] == {}
    assert not measured.calls[1]["usage_complete"]
    assert not measured.usage_complete
    assert estimate(measured.usage, card(), usage_complete=measured.usage_complete)["amount"] is None


def test_explicit_reported_zero_is_distinguishable_from_missing_usage():
    measured = metered_openai([vector_reply({"prompt_tokens": 0})])
    measured.embed(["explicit-zero"])
    assert measured.calls[0]["usage_delta"] == {"prompt_tokens": 0}
    assert measured.usage_report_counts == {"prompt_tokens": 1}
    assert measured.usage_complete
    assert estimate(measured.usage, card(), usage_complete=True)["amount"] == 0


def test_native_partial_batch_usage_is_not_complete_or_free_and_has_utc_timestamps():
    def native(count, usage=None):
        result = {"output": {"embeddings": [{"text_index": i, "embedding": [1., 0.]} for i in range(count)]}}
        if usage is not None:
            result["usage"] = usage
        return result
    provider = DashScopeEmbeddingProvider(ProviderConfig(base_url="https://synthetic.invalid", api_key="not-a-real-key", embedding_model="test-model", embedding_dimensions=2))
    provider._client._opener = Responses([native(20, {"input_tokens": 40}), native(1)])
    measured = MeasuredEmbedder(provider, live=True)
    measured.embed([f"text-{i}" for i in range(21)])
    call = measured.calls[0]
    assert call["remote_request_delta"] == 2
    assert call["usage_delta"] == {"input_tokens": 40}
    assert call["usage_report_counts"] == {"input_tokens": 1}
    assert not call["usage_complete"] and not measured.usage_complete
    assert datetime.fromisoformat(call["started_at"]).utcoffset().total_seconds() == 0
    assert datetime.fromisoformat(call["ended_at"]) >= datetime.fromisoformat(call["started_at"])


def test_native_usage_still_counts_a_reported_paid_response_when_vectors_are_invalid():
    provider = DashScopeEmbeddingProvider(ProviderConfig(base_url="https://synthetic.invalid", api_key="not-a-real-key", embedding_model="test-model", embedding_dimensions=2))
    provider._client._opener = Responses([{"usage": {"input_tokens": 9}, "output": {"embeddings": [{"text_index": 0, "embedding": [float("nan"), 1]}]}}])
    measured = MeasuredEmbedder(provider, live=True)
    with pytest.raises(ValueError):
        measured.embed(["paid-but-invalid"])
    # Invalid JSON constants still fail transport before usage can be trusted.
    # A schema-valid but invalid vector is separately covered below.
    provider._client._opener = Responses([{"usage": {"input_tokens": 9}, "output": {"embeddings": [{"text_index": 0, "embedding": [0, 0]}]}}])
    with pytest.raises(ValueError):
        measured.embed(["paid-but-zero-vector"])
    assert provider.usage["input_tokens"] == 9
    assert measured.calls[-1]["usage_delta"] == {"input_tokens": 9}
    assert measured.calls[-1]["usage_complete"]
    assert not measured.usage_complete  # The first request had no valid usage JSON.


def test_malformed_counters_do_not_mask_original_embedding_exception():
    class Provider:
        fingerprint = "fp"
        request_count = 0
        usage = {"input_tokens": "bad"}
        def embed(self, texts):
            self.usage = {"input_tokens": False}
            raise RuntimeError("original synthetic embedding failure")
    measured = MeasuredEmbedder(Provider(), live=True)
    with pytest.raises(RuntimeError, match="original synthetic"):
        measured.embed(["test"])
    assert measured.calls[0]["error_type"] == "RuntimeError"
    assert not measured.calls[0]["usage_complete"]


def test_meter_only_reports_requests_and_tokens_since_its_own_construction():
    measured = metered_openai([vector_reply({"prompt_tokens": 10}), vector_reply({"prompt_tokens": 3})])
    measured.provider.embed(["before-wrapping-again"])
    fresh = MeasuredEmbedder(measured.provider, live=True)
    fresh.embed_query("after")
    assert fresh.request_count == 1 and fresh.usage == {"prompt_tokens": 3}
    assert fresh.usage_report_counts == {"prompt_tokens": 1}
    assert fresh.usage_complete


@pytest.mark.parametrize("rate", ["1e1000000", "1e-1000000", "1e-1000"])
def test_price_numeric_overflow_or_underflow_is_unknown_instead_of_throwing_or_free(rate):
    result = estimate({"input_tokens": 1}, card(input_per_million=rate))
    assert result["amount"] is None
    assert result["status"] == "estimate_out_of_numeric_range"


def test_complete_false_and_unknown_operation_never_emit_a_numeric_estimate():
    assert estimate({"input_tokens": 0}, card(), usage_complete=False)["amount"] is None
    assert estimate({"input_tokens": 100}, card(), operation="typo")["status"] == "unsupported_operation"
