"""Real localhost HTTP protocol tests; no external service or paid request."""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time

import pytest

from repomind.domain.models import Event
from repomind.intelligence.models import ExtractionBatch, SourceMessage
from repomind.intelligence.providers import OpenAICompatibleProvider, ProviderConfig, _SYSTEM_PROMPT, extraction_json_schema


def source():
    return SourceMessage(project_id="A", source_id="source", observed_at="2026-05-01T00:00:00Z", text="数据库已经迁移到 PostgreSQL。")


def extraction_body():
    return {"facts": [{"subject": "project", "predicate": "database", "value": "PostgreSQL", "event_type": "complete", "effective_at": None, "supersedes_event_id": None, "evidence_text": "已经迁移到 PostgreSQL"}], "abstain_reason": None}


def completion(content=None, **changes):
    result = {"choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": json.dumps(extraction_body(), ensure_ascii=False) if content is None else content}}]}
    result.update(changes)
    return result


@contextmanager
def endpoint(responses):
    requests = []
    queue = list(responses)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(body)})
            reply = queue.pop(0)
            if callable(reply):
                reply = reply()
            status, payload, extra_headers = reply
            encoded = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
            try:
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                for key, value in extra_headers.items():
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def config(url, **changes):
    options = {"base_url": url, "api_key": "localhost-test-key", "chat_model": "chat-test", "embedding_model": "embedding-test"}
    options.update(changes)
    return ProviderConfig(**options)


def test_config_key_is_hidden_from_repr_serialization_and_safe_metadata():
    settings = config("https://api.example.test/v1", api_key="secret-do-not-log")
    provider = OpenAICompatibleProvider(settings)
    for data in [repr(settings), settings.model_dump_json(), str(settings.safe_metadata()), str(provider.safe_metadata()), provider.name, provider.fingerprint]:
        assert "secret-do-not-log" not in data
    assert "api_key" not in settings.model_dump()


def test_usage_counts_only_actual_nonnegative_integer_fields():
    responses = [(200, completion(usage={"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}), {}), (200, completion(usage={"prompt_tokens": 5, "completion_tokens": True, "total_tokens": -1}), {})]
    with endpoint(responses) as (url, requests):
        provider = OpenAICompatibleProvider(config(url))
        provider.extract(source(), [])
        provider.extract(source(), [])
        assert provider.request_count == 2
        assert provider.usage == {"prompt_tokens": 15, "completion_tokens": 3, "total_tokens": 13}
        assert provider.safe_metadata()["usage"] == provider.usage


@pytest.mark.parametrize("url", ["http://example.com/v1", "file:///tmp/keys", "https://name:password@example.com/v1", "https://example.com/v1?key=secret", "https://example.com/v1#fragment", "https://good.test\\@evil.test/v1", "https://example.com:bad/v1", "http://localhost.evil.test/v1", "https://exam\nple.com/v1"])
def test_config_rejects_unsafe_endpoints(url):
    with pytest.raises(ValueError):
        config(url)


@pytest.mark.parametrize("url", ["http://127.0.0.1:1234/v1", "http://localhost:1234/v1", "http://[::1]:1234/v1", "https://example.com/v1"])
def test_explicit_loopback_http_and_https_are_allowed(url):
    assert config(url).base_url == url


def test_config_validation_error_does_not_echo_bad_secret():
    with pytest.raises(ValueError) as raised:
        config("https://example.com/v1", api_key="bad-secret\nheader")
    assert "bad-secret" not in str(raised.value)


def test_from_env_loads_deepseek_profile_without_embedding_fallback(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    names = ["REPOMIND_PROVIDER", "REPOMIND_BASE_URL", "OPENAI_BASE_URL", "REPOMIND_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "REPOMIND_CHAT_MODEL", "REPOMIND_CHAT_FORMAT", "REPOMIND_TIMEOUT_SECONDS", "REPOMIND_MAX_COMPLETION_TOKENS", "REPOMIND_EMBEDDING_BASE_URL", "REPOMIND_EMBEDDING_API_KEY", "REPOMIND_EMBEDDING_MODEL"]
    for name in names:
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text("REPOMIND_PROVIDER=deepseek\nDEEPSEEK_API_KEY=local-test-key\nREPOMIND_CHAT_MODEL=deepseek-flash\nREPOMIND_CHAT_FORMAT=json_object\nREPOMIND_TIMEOUT_SECONDS=60\n", encoding="utf-8")
    settings = ProviderConfig.from_env()
    assert settings.api_style == "deepseek"
    assert settings.base_url == "https://api.deepseek.com"
    assert settings.chat_model == "deepseek-flash"
    assert settings.embedding_model is None
    assert settings.timeout_seconds == 60
    with pytest.raises(ValueError, match="independent REPOMIND_EMBEDDING"):
        ProviderConfig.embedding_from_env()
    monkeypatch.setenv("REPOMIND_EMBEDDING_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setenv("REPOMIND_EMBEDDING_API_KEY", "embedding-only-key")
    monkeypatch.setenv("REPOMIND_EMBEDDING_MODEL", "embedding-test")
    embed_config = ProviderConfig.embedding_from_env()
    assert embed_config.chat_model is None
    assert embed_config.api_style == "openai"
    assert embed_config.api_key.get_secret_value() == "embedding-only-key"


def test_deepseek_profile_never_borrows_global_openai_credentials_or_url(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for name in ["REPOMIND_API_KEY", "REPOMIND_BASE_URL", "REPOMIND_CHAT_MODEL", "REPOMIND_CHAT_FORMAT", "DEEPSEEK_API_KEY", "REPOMIND_TIMEOUT_SECONDS", "REPOMIND_MAX_COMPLETION_TOKENS"]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("REPOMIND_PROVIDER", "deepseek")
    monkeypatch.setenv("OPENAI_API_KEY", "unrelated-openai-secret")
    monkeypatch.setenv("OPENAI_BASE_URL", "https://unrelated-openai.example/v1")
    settings = ProviderConfig.from_env()
    assert settings.api_key is None
    assert settings.base_url == "https://api.deepseek.com"


def test_strict_schema_requires_every_field_and_forbids_extras():
    schema = extraction_json_schema()
    fact_schema = schema["properties"]["facts"]["items"]
    assert set(schema["required"]) == set(schema["properties"])
    assert set(fact_schema["required"]) == set(fact_schema["properties"])
    assert schema["additionalProperties"] is fact_schema["additionalProperties"] is False
    assert "format" not in json.dumps(schema)


def test_chat_protocol_strict_json_schema_no_tools_or_temperature():
    with endpoint([(200, completion(), {})]) as (url, requests):
        provider = OpenAICompatibleProvider(config(url))
        batch = provider.extract(source(), [])
    assert batch.facts[0].value == "PostgreSQL"
    request = requests[0]
    assert request["path"] == "/v1/chat/completions"
    assert request["headers"]["Authorization"] == "Bearer localhost-test-key"
    payload = request["body"]
    assert payload["model"] == "chat-test"
    assert payload["response_format"]["json_schema"]["strict"] is True
    assert payload["max_completion_tokens"] == 2048
    assert "temperature" not in payload and "tools" not in payload
    assert payload["stream"] is False
    assert "untrusted DATA" in payload["messages"][0]["content"]
    assert "exact evidence_text substrings" in payload["messages"][0]["content"]


def test_deepseek_protocol_uses_json_object_max_tokens_and_disabled_thinking():
    with endpoint([(200, completion(), {})]) as (url, requests):
        provider = OpenAICompatibleProvider(config(url, api_style="deepseek", chat_model="deepseek-flash", chat_format="json_object"))
        provider.extract(source(), [])
    payload = requests[0]["body"]
    assert payload["response_format"] == {"type": "json_object"}
    assert payload["max_tokens"] == 2048
    assert "max_completion_tokens" not in payload
    assert payload["thinking"] == {"type": "disabled"}
    assert "JSON schema:" in payload["messages"][0]["content"]
    assert '"facts": []' in payload["messages"][0]["content"]
    assert "temperature" not in payload


def test_positive_prompt_example_is_valid_json_with_two_complete_candidates():
    encoded = _SYSTEM_PROMPT.split("Positive JSON example:\n", 1)[1].split("\nEnd positive JSON example.", 1)[0]
    example = json.loads(encoded)
    batch = ExtractionBatch.model_validate(example)
    assert [fact.event_type for fact in batch.facts] == ["declare", "plan"]
    assert batch.abstain_reason is None
    assert len(batch.facts) == 2
    fields = {"subject", "predicate", "value", "event_type", "effective_at", "supersedes_event_id", "evidence_text"}
    sample_source = _SYSTEM_PROMPT.split("Illustrative positive source example:\n", 1)[1].split("\nPositive JSON example:", 1)[0]
    for fact in example["facts"]:
        assert set(fact) == fields
        assert fact["effective_at"] is fact["supersedes_event_id"] is None
        assert fact["evidence_text"] in sample_source


def test_schema_diagnostics_include_at_most_five_locations_and_types_without_inputs():
    marker = "secret-input-must-never-appear"
    fact = {"subject": {"input": marker}, "predicate": [marker], "value": {"input": marker},
            "event_type": marker, "effective_at": marker, "supersedes_event_id": [marker], "evidence_text": 42}
    body = completion(json.dumps({"facts": [fact], "abstain_reason": None}))
    with endpoint([(200, body, {})]) as (url, requests):
        with pytest.raises(ValueError) as raised:
            OpenAICompatibleProvider(config(url)).extract(source(), [])
    message = str(raised.value)
    assert "candidate schema:" in message
    details = json.loads(message.split(": ", 1)[1])
    assert len(details) == 5
    assert all(set(item) == {"loc", "type"} for item in details)
    assert any(item["loc"] == ["facts", 0, "event_type"] and item["type"] == "literal_error" for item in details)
    assert marker not in message
    assert "localhost-test-key" not in message
    assert source().text not in message


def test_schema_diagnostics_redact_untrusted_extra_property_names():
    marker = "secret-field-name-must-never-appear"
    extracted = extraction_body()
    extracted["facts"][0][marker] = "sensitive extra value"
    with endpoint([(200, completion(json.dumps(extracted)), {})]) as (url, requests):
        with pytest.raises(ValueError) as raised:
            OpenAICompatibleProvider(config(url)).extract(source(), [])
    message = str(raised.value)
    assert marker not in message
    assert "sensitive extra value" not in message
    details = json.loads(message.split(": ", 1)[1])
    assert details == [{"loc": ["facts", 0, "<extra_field>"], "type": "extra_forbidden"}]


def test_json_parse_error_is_distinct_and_does_not_echo_content():
    marker = "secret-malformed-json-must-never-appear"
    with endpoint([(200, completion('{"facts":' + marker), {})]) as (url, requests):
        with pytest.raises(ValueError) as raised:
            OpenAICompatibleProvider(config(url)).extract(source(), [])
    assert str(raised.value) == "provider extraction content is invalid JSON"
    assert marker not in str(raised.value)


@pytest.mark.parametrize("kind", ["refusal", "length", "tool", "invalid_json", "extra_field", "bad_quote", "multiple_choices"])
def test_chat_rejects_unsafe_or_invalid_model_output(kind):
    body = completion()
    choice = body["choices"][0]
    if kind == "refusal":
        choice["message"]["refusal"] = "Refused"
    elif kind == "length":
        choice["finish_reason"] = "length"
    elif kind == "tool":
        choice["message"]["tool_calls"] = [{"function": {"name": "exec"}}]
    elif kind == "invalid_json":
        choice["message"]["content"] = "```json\n{}\n```"
    elif kind == "extra_field":
        extracted = extraction_body()
        extracted["facts"][0]["project_id"] = "B"
        choice["message"]["content"] = json.dumps(extracted)
    elif kind == "bad_quote":
        extracted = extraction_body()
        extracted["facts"][0]["evidence_text"] = "fabricated quote"
        choice["message"]["content"] = json.dumps(extracted)
    elif kind == "multiple_choices":
        body["choices"].append(choice.copy())
    with endpoint([(200, body, {})]) as (url, requests):
        with pytest.raises(ValueError):
            OpenAICompatibleProvider(config(url)).extract(source(), [])
    assert len(requests) == 1


def test_http_errors_do_not_echo_secret_upstream_body_and_redirects_are_not_followed():
    for status, headers in [(401, {}), (307, {"Location": "http://127.0.0.1:9/steal-key"})]:
        with endpoint([(status, b"upstream leaked localhost-test-key secret-body", headers)]) as (url, requests):
            with pytest.raises(ValueError) as raised:
                OpenAICompatibleProvider(config(url)).extract(source(), [])
        assert str(status) in str(raised.value)
        assert "localhost-test-key" not in str(raised.value)
        assert "secret-body" not in str(raised.value)
        assert len(requests) == 1


def test_response_limit_is_enforced():
    with endpoint([(200, b"x" * 1000, {})]) as (url, requests):
        with pytest.raises(ValueError, match="limit"):
            OpenAICompatibleProvider(config(url, max_response_bytes=64)).extract(source(), [])


def test_request_limit_is_enforced_before_network():
    with endpoint([]) as (url, requests):
        with pytest.raises(ValueError, match="request exceeds"):
            OpenAICompatibleProvider(config(url, max_request_bytes=64)).extract(source(), [])
        assert requests == []


def test_timeout_is_enforced_without_exposing_connection_details():
    def delayed():
        time.sleep(0.15)
        return 200, completion(), {}
    with endpoint([delayed]) as (url, requests):
        with pytest.raises(ValueError, match="timed out"):
            OpenAICompatibleProvider(config(url, timeout_seconds=0.02)).extract(source(), [])


def test_missing_model_or_key_and_mixed_project_context_fail_before_http():
    with endpoint([]) as (url, requests):
        with pytest.raises(ValueError, match="chat model"):
            OpenAICompatibleProvider(config(url, chat_model=None)).extract(source(), [])
        with pytest.raises(ValueError, match="API key"):
            OpenAICompatibleProvider(config(url, api_key=None)).extract(source(), [])
        other = Event(event_id="other", project_id="B", source_id="other-source", subject="project", predicate="database", value="SQLite", event_type="declare", observed_at="2026-01-01T00:00:00Z")
        with pytest.raises(ValueError, match="only the source project"):
            OpenAICompatibleProvider(config(url)).extract(source(), [other])
        assert requests == []


def test_embeddings_are_reordered_by_index_and_fingerprints_exclude_credentials():
    response = {"data": [{"index": 1, "embedding": [0, 1]}, {"index": 0, "embedding": [1, 0]}]}
    with endpoint([(200, response, {})]) as (url, requests):
        provider = OpenAICompatibleProvider(config(url))
        assert provider.embed(["database", "cache"]) == [[1.0, 0.0], [0.0, 1.0]]
        assert provider.embedding_dimension == 2
        assert requests[0]["path"] == "/v1/embeddings"
        assert requests[0]["body"]["encoding_format"] == "float"
        assert provider.fingerprint == OpenAICompatibleProvider(config(url, api_key="another-test-key")).fingerprint
        assert provider.fingerprint != OpenAICompatibleProvider(config(url, embedding_model="different")).fingerprint


@pytest.mark.parametrize("data", [
    [],
    [{"index": 0, "embedding": [1.0, 0]}, {"index": 0, "embedding": [0, 1.0]}],
    [{"index": True, "embedding": [1.0, 0]}],
    [{"index": 3, "embedding": [1.0, 0]}],
    [{"index": 0, "embedding": [0, 0]}],
    [{"index": 0, "embedding": ["1", 0]}],
    [{"index": 0, "embedding": [True, 0]}],
    [{"index": 0, "embedding": [float("nan"), 1]}],
    [{"index": 0, "embedding": [float("inf"), 1]}],
    [{"index": 0, "embedding": []}],
])
def test_embedding_response_validation_rejects_bad_count_indices_or_vectors(data):
    with endpoint([(200, {"data": data}, {})]) as (url, requests):
        with pytest.raises(ValueError):
            OpenAICompatibleProvider(config(url)).embed(["query"])


def test_embedding_dimensions_must_be_consistent_and_match_configuration():
    mixed = {"data": [{"index": 0, "embedding": [1, 0]}, {"index": 1, "embedding": [1, 0, 0]}]}
    with endpoint([(200, mixed, {})]) as (url, requests):
        with pytest.raises(ValueError, match="mixed"):
            OpenAICompatibleProvider(config(url)).embed(["one", "two"])
    with endpoint([(200, {"data": [{"index": 0, "embedding": [1, 0]}]}, {})]) as (url, requests):
        with pytest.raises(ValueError, match="configured dimensions"):
            OpenAICompatibleProvider(config(url, embedding_dimensions=3)).embed(["one"])


def test_embedding_duplicate_indices_are_rejected_even_with_correct_count():
    response = {"data": [{"index": 0, "embedding": [1, 0]}, {"index": 0, "embedding": [0, 1]}]}
    with endpoint([(200, response, {})]) as (url, requests):
        with pytest.raises(ValueError, match="indices must be unique"):
            OpenAICompatibleProvider(config(url)).embed(["one", "two"])


def test_embedding_dimension_cannot_change_between_requests():
    responses = [(200, {"data": [{"index": 0, "embedding": [1, 0]}]}, {}), (200, {"data": [{"index": 0, "embedding": [1, 0, 0]}]}, {})]
    with endpoint(responses) as (url, requests):
        provider = OpenAICompatibleProvider(config(url))
        provider.embed(["first"])
        with pytest.raises(ValueError, match="changed during this session"):
            provider.embed(["second"])


def test_deepseek_chat_configuration_never_sends_an_embedding_request():
    with endpoint([]) as (url, requests):
        with pytest.raises(ValueError, match="independent embedding provider"):
            OpenAICompatibleProvider(config(url, api_style="deepseek")).embed(["query"])
        assert requests == []
    with pytest.raises(ValueError, match="independent embedding provider"):
        OpenAICompatibleProvider(config("https://api.deepseek.com")).embed(["query"])
