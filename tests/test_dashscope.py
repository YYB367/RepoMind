"""DashScope native HTTP contract against localhost only, using fake credentials."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading

import pytest

from repomind.intelligence.dashscope import DashScopeEmbeddingProvider
from repomind.intelligence.providers import ProviderConfig


MODEL = "qwen3.7-text-embedding-flash"
FAKE_KEY = "synthetic-dashscope-test-credential"
SUFFIX = "/services/embeddings/text-embedding/text-embedding"


def vector(seed=1.0, dimension=1024):
    return [float(seed)] + [0.0] * (dimension - 1)


def response(vectors, usage=None):
    result = {"output": {"embeddings": [
        {"text_index": index, "embedding": item} for index, item in enumerate(vectors)
    ]}, "request_id": "synthetic-local-request"}
    if usage is not None:
        result["usage"] = usage
    return result


@contextmanager
def endpoint(replies):
    requests, pending = [], list(replies)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            record = {"path": self.path, "headers": dict(self.headers), "body": json.loads(body)}
            requests.append(record)
            reply = pending.pop(0)
            status, payload = reply(record) if callable(reply) else reply
            encoded = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def config(url, **changes):
    values = {"base_url": url, "api_key": FAKE_KEY, "embedding_model": MODEL}
    values.update(changes)
    return ProviderConfig(**values)


def test_document_request_uses_native_endpoint_original_model_and_dense_1024_parameters():
    with endpoint([(200, response([vector(), vector(2)]))]) as (url, requests):
        provider = DashScopeEmbeddingProvider(config(url))
        result = provider.embed(["数据库", "deployment"])
        assert [item[0] for item in result] == [1, 2]
        assert all(len(item) == 1024 for item in result)
        assert provider.embedding_dimension == 1024
        assert provider.request_count == 1
    assert requests[0]["path"] == "/api/v1" + SUFFIX
    assert requests[0]["body"] == {
        "model": MODEL, "input": {"texts": ["数据库", "deployment"]},
        "parameters": {"text_type": "document", "dimension": 1024, "output_type": "dense"},
    }
    assert requests[0]["headers"]["Authorization"] == "Bearer " + FAKE_KEY
    assert requests[0]["headers"]["Content-Type"] == "application/json"


def test_query_request_uses_single_text_query_type_and_returns_one_vector():
    with endpoint([(200, response([vector(3)]))]) as (url, requests):
        provider = DashScopeEmbeddingProvider(config(url))
        result = provider.embed_query("Which storage engine?")
        assert result == vector(3)
    assert requests[0]["body"]["input"] == {"texts": ["Which storage engine?"]}
    assert requests[0]["body"]["parameters"] == {
        "text_type": "query", "dimension": 1024, "output_type": "dense",
    }


def test_batches_at_most_twenty_and_reorders_each_text_index_without_losing_global_order():
    def respond(record):
        texts = record["body"]["input"]["texts"]
        payload = response([vector(int(text.split("-")[1]) + 1) for text in texts],
                           usage={"total_tokens": len(texts) * 2})
        payload["output"]["embeddings"].reverse()
        return 200, payload

    with endpoint([respond, respond, respond]) as (url, requests):
        provider = DashScopeEmbeddingProvider(config(url))
        result = provider.embed([f"document-{index}" for index in range(41)])
        assert [item[0] for item in result] == list(range(1, 42))
        assert provider.request_count == 3
        assert provider.usage["total_tokens"] == 82
    assert [len(record["body"]["input"]["texts"]) for record in requests] == [20, 20, 1]
    assert all(record["body"]["parameters"]["text_type"] == "document" for record in requests)


def test_native_token_usage_counts_only_reported_nonnegative_integers():
    replies = [
        (200, response([vector()], usage={"input_tokens": 5, "total_tokens": 7, "estimated_dollars": 1})),
        (200, response([vector()], usage={"input_tokens": True, "total_tokens": 8, "prompt_tokens": -2})),
    ]
    with endpoint(replies) as (url, requests):
        provider = DashScopeEmbeddingProvider(config(url))
        provider.embed(["document"])
        provider.embed_query("query")
        assert provider.usage["input_tokens"] == 5
        assert provider.usage["total_tokens"] == 15
        assert "estimated_dollars" not in provider.usage
        assert "prompt_tokens" not in provider.usage
        assert provider.safe_metadata()["usage"] == provider.usage
        assert provider.safe_metadata()["request_count"] == 2


def test_metadata_and_fingerprint_do_not_contain_credentials_and_model_identity_changes_cache_key():
    first = DashScopeEmbeddingProvider(config("https://example.invalid/api/v1"))
    changed_key = DashScopeEmbeddingProvider(config("https://example.invalid/api/v1", api_key="another-synthetic-key"))
    changed_model = DashScopeEmbeddingProvider(config("https://example.invalid/api/v1", embedding_model=MODEL + "-test-model"))
    changed_size = DashScopeEmbeddingProvider(config("https://example.invalid/api/v1", embedding_dimensions=512))
    assert first.fingerprint == changed_key.fingerprint
    assert first.fingerprint != changed_model.fingerprint
    assert first.fingerprint != changed_size.fingerprint
    for text in (repr(first.config), first.config.model_dump_json(),
                 json.dumps(first.safe_metadata()), first.fingerprint, first.name):
        assert FAKE_KEY not in text
    assert first.request_count == 0


def test_empty_document_batch_makes_no_network_request():
    with endpoint([]) as (url, requests):
        provider = DashScopeEmbeddingProvider(config(url))
        assert provider.embed([]) == []
        assert provider.request_count == 0
    assert requests == []


@pytest.mark.parametrize("texts", [[""], [" "], [123], "not-a-list"])
def test_invalid_document_input_fails_before_http(texts):
    with endpoint([]) as (url, requests):
        provider = DashScopeEmbeddingProvider(config(url))
        with pytest.raises(ValueError):
            provider.embed(texts)
        assert provider.request_count == 0
    assert requests == []


@pytest.mark.parametrize("text", ["", " ", ["not-a-string"]])
def test_invalid_query_input_fails_before_http(text):
    with endpoint([]) as (url, requests):
        provider = DashScopeEmbeddingProvider(config(url))
        with pytest.raises(ValueError):
            provider.embed_query(text)
        assert provider.request_count == 0
    assert requests == []


@pytest.mark.parametrize("case", ["mixed-dimensions", "wrong-configured-dimension", "nan", "zero", "boolean-component",
                                   "duplicate-index", "missing-record", "out-of-range-index", "string-index"])
def test_native_embedding_validation_rejects_invalid_vectors_counts_or_indices(case):
    payload = response([vector(), vector(2)])
    rows = payload["output"]["embeddings"]
    if case == "mixed-dimensions":
        rows[1]["embedding"] = vector(dimension=512)
    elif case == "wrong-configured-dimension":
        rows[0]["embedding"] = rows[1]["embedding"] = vector(dimension=512)
    elif case == "nan":
        rows[0]["embedding"][0] = float("nan")
    elif case == "zero":
        rows[0]["embedding"] = [0.0] * 1024
    elif case == "boolean-component":
        rows[0]["embedding"][0] = True
    elif case == "duplicate-index":
        rows[1]["text_index"] = 0
    elif case == "missing-record":
        rows.pop()
    elif case == "out-of-range-index":
        rows[1]["text_index"] = 2
    elif case == "string-index":
        rows[1]["text_index"] = "1"
    with endpoint([(200, payload)]) as (url, requests):
        provider = DashScopeEmbeddingProvider(config(url))
        with pytest.raises(ValueError):
            provider.embed(["one", "two"])
        assert provider.request_count == 1


def test_http_200_error_code_is_rejected_without_echoing_service_message_even_with_output():
    payload = response([vector()])
    payload.update({"code": "SyntheticServiceFailure", "message": "upstream echoed " + FAKE_KEY})
    with endpoint([(200, payload)]) as (url, requests):
        provider = DashScopeEmbeddingProvider(config(url))
        with pytest.raises(ValueError) as raised:
            provider.embed(["document"])
        assert FAKE_KEY not in str(raised.value)
        assert provider.request_count == 1


def test_http_failure_does_not_echo_fake_credential_or_upstream_body():
    with endpoint([(429, {"code": "Throttled", "message": "upstream echoed " + FAKE_KEY})]) as (url, requests):
        provider = DashScopeEmbeddingProvider(config(url))
        with pytest.raises(ValueError) as raised:
            provider.embed(["document"])
        assert "429" in str(raised.value)
        assert FAKE_KEY not in str(raised.value)
        assert "upstream echoed" not in str(raised.value)
        assert provider.request_count == 1


def test_configured_dimension_is_sent_and_enforced_without_model_substitution():
    with endpoint([(200, response([vector(4, dimension=512)]))]) as (url, requests):
        provider = DashScopeEmbeddingProvider(config(url, embedding_dimensions=512))
        assert len(provider.embed(["document"])[0]) == 512
    assert requests[0]["body"]["parameters"]["dimension"] == 512
    assert requests[0]["body"]["model"] == MODEL
