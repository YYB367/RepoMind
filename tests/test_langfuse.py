"""Fake-client state tests plus real SDK 5 over a local OTLP/REST server.

Nothing in this module loads the project .env or contacts a cloud service.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
import gzip
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import json
import threading
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import uuid

import pytest

from repomind.platform.langfuse import LangfuseConfig, LangfuseExporter
from repomind.platform.tracing import TraceOutbox, TraceRecord


def record(**changes):
    values = {"run_id": "run-1", "item_id": "case-1", "provider": "self", "project_id": "A", "stage": "query",
              "synthetic": True, "input": {"question": "database"}, "output": {"value": "MySQL"},
              "expected_output": {"value": "MySQL"}, "scores": {"correct": 1.0},
              "observations": [{"name": "resolve", "elapsed_seconds": 0.04},
                               {"name": "recorded-generation", "as_type": "generation", "elapsed_seconds": 0.3,
                                "input": "synthetic prompt", "output": "synthetic response", "model": "contract-test-model",
                                "usage_details": {"input": 3, "output": 2}, "cost_details": None}]}
    values.update(changes)
    return TraceRecord(**values)


def config(**changes):
    values = {"base_url": "https://langfuse.example.test", "public_key": "public-test-1", "secret_key": "private-test-1"}
    values.update(changes)
    return LangfuseConfig(**values)


class FakeSpan:
    def __init__(self, client, arguments):
        self.client, self.arguments = client, arguments
        self.id = f"{client.sequence:016x}"
        client.sequence += 1
        self.trace_id = arguments.get("trace_context", {}).get("trace_id") or (client.stack[-1].trace_id if client.stack else f"{client.sequence:032x}")
        self.metadata = dict(arguments.get("metadata", {}))
        self.output = arguments.get("output")

    def __enter__(self):
        self.client.stack.append(self)
        return self

    def __exit__(self, *args):
        self.client.stack.pop()
        self.client.observations.append({"id": self.id, "trace_id": self.trace_id,
            "type": self.arguments.get("as_type", "span").upper(), "name": self.arguments["name"],
            "input": self.arguments.get("input"), "output": self.output, "metadata": dict(self.metadata),
            "model": self.arguments.get("model"), "usage_details": self.arguments.get("usage_details"),
            "cost_details": self.arguments.get("cost_details")})

    def start_as_current_observation(self, **kwargs):
        return FakeSpan(self.client, kwargs)


class FakeClient:
    def __init__(self):
        self.sequence = 1
        self.stack, self.observations, self.scores, self.experiment_items = [], [], [], []
        self.calls, self.dataset_calls = [], []
        self.visible, self.read_error, self.experiment_calls = True, None, 0
        self.api = SimpleNamespace(observations=SimpleNamespace(get_many=self.read_observations),
                                   scores=SimpleNamespace(get_many=self.read_scores),
                                   experiments=SimpleNamespace(list_items=self.read_experiments))

    def start_as_current_observation(self, **kwargs):
        self.calls.append(("start", kwargs))
        return FakeSpan(self, kwargs)

    def update_current_span(self, **kwargs):
        self.stack[-1].metadata.update(kwargs.get("metadata", {}))

    def create_score(self, **kwargs):
        self.calls.append(("score", kwargs))
        self.scores.append({"id": kwargs.get("score_id", str(len(self.scores))), "name": kwargs["name"],
            "value": kwargs["value"], "data_type": kwargs.get("data_type", "NUMERIC"),
            "metadata": kwargs.get("metadata", {}), "subject": {"kind": "trace", "id": kwargs["trace_id"]}})

    def flush(self):
        self.calls.append(("flush", {}))

    def read_observations(self, **kwargs):
        self.calls.append(("read_observations", kwargs))
        if self.read_error:
            raise self.read_error
        return {"data": [row for row in self.observations if row["trace_id"] == kwargs["trace_id"]] if self.visible else [], "meta": {}}

    def read_scores(self, **kwargs):
        self.calls.append(("read_scores", kwargs))
        assert kwargs["fields"] == "subject,details"
        return {"data": [row for row in self.scores if row["subject"]["id"] == kwargs["trace_id"]] if self.visible else [], "meta": {}}

    def read_experiments(self, **kwargs):
        self.calls.append(("read_experiments", kwargs))
        return {"data": [row for row in self.experiment_items if row["experiment_id"] == kwargs["experiment_id"]] if self.visible else [], "meta": {}}

    def create_dataset(self, **kwargs):
        self.dataset_calls.append(kwargs)
        return SimpleNamespace(id="dataset-local", **kwargs)

    def create_dataset_item(self, **kwargs):
        return SimpleNamespace(dataset_id="dataset-local", **kwargs)

    def run_experiment(self, **kwargs):
        self.experiment_calls += 1
        results = []
        for item in kwargs["data"]:
            with self.start_as_current_observation(name="experiment-item-task", input=item.input) as span:
                output = kwargs["task"](item=item)
                span.output = output
                for evaluator in kwargs["evaluators"]:
                    scores = evaluator(input=item.input, output=output, expected_output=item.expected_output, metadata=item.metadata)
                    for score in scores:
                        self.create_score(trace_id=span.trace_id, **score)
                self.experiment_items.append({"trace_id": span.trace_id, "experiment_id": kwargs["experiment_id"],
                    "experiment_item_id": item.id, "input": item.input, "output": output,
                    "expected_output": item.expected_output, "metadata": dict(span.metadata)})
                results.append(SimpleNamespace(output=output, trace_id=span.trace_id))
        return SimpleNamespace(item_results=results)


def test_config_never_reads_dotenv_or_serializes_credentials(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for name in ("LANGFUSE_BASE_URL", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / ".env").write_text("LANGFUSE_SECRET_KEY=do-not-load-this-file\n", encoding="utf-8")
    with pytest.raises(ValueError):
        LangfuseConfig.from_env()
    settings = config()
    assert "public-test-1" not in repr(settings) + settings.model_dump_json() + str(settings.safe_metadata())
    assert "private-test-1" not in repr(settings) + settings.model_dump_json() + str(settings.safe_metadata())
    assert settings.target_id == config(secret_key="rotated-private").target_id
    assert settings.target_id != config(public_key="other-public").target_id
    assert settings.target_id != config(base_url="https://other.example.test").target_id


def test_close_is_idempotent_and_never_constructs_an_unused_client(monkeypatch):
    empty = LangfuseExporter(config())
    monkeypatch.setattr(empty, "_client", lambda: pytest.fail("close constructed an SDK client"))
    empty.close()
    empty.close()
    calls = []
    client = SimpleNamespace(shutdown=lambda: calls.append("closed"))
    used = LangfuseExporter(config(), client)
    used.close()
    used.close()
    assert calls == ["closed"]


def test_trace_sync_requires_read_back_then_recovers_without_resending(tmp_path):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    item = record()
    box.append(item)
    client = FakeClient()
    client.visible = False
    exporter = LangfuseExporter(config(), client, verify_attempts=1, verify_delay_seconds=0)
    result = exporter.sync(box)
    assert result["sent_unconfirmed"] == 1
    assert not result["cloud_verified"]
    assert box.state(item.trace_id, exporter.target_id)["status"] == "sent_unconfirmed"
    emitted = len(client.observations)
    client.visible = True
    recovered = exporter.sync(box)
    assert recovered["cloud_verified"]
    assert len(client.observations) == emitted
    assert box.state(item.trace_id, exporter.target_id)["attempts"] == 1
    reads = sum(name == "read_observations" for name, _ in client.calls)
    again = LangfuseExporter(config(secret_key="rotated-private"), client).sync(box)
    assert again["cloud_verified"]
    assert len(client.observations) == emitted
    assert sum(name == "read_observations" for name, _ in client.calls) > reads


def test_target_change_does_not_reuse_another_projects_ack(tmp_path):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    item = record()
    box.append(item)
    first = LangfuseExporter(config(), FakeClient())
    assert first.sync(box)["cloud_verified"]
    second_client = FakeClient()
    second = LangfuseExporter(config(public_key="other-project-public"), second_client)
    assert box.state(item.trace_id, second.target_id)["status"] == "pending"
    assert second.sync(box)["cloud_verified"]
    assert second_client.observations


def test_export_failures_are_safe_retryable_and_do_not_echo_upstream_secrets(tmp_path):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    item = record()
    box.append(item)
    client = FakeClient()
    client.read_error = RuntimeError("private-test-1 upstream body must never appear")
    exporter = LangfuseExporter(config(), client)
    result = exporter.sync(box)
    assert result["failed"] == 1 and not result["cloud_verified"]
    assert "private-test-1" not in json.dumps(result)
    assert "upstream body" not in box.receipts_path.read_text(encoding="utf-8")
    client.read_error = None
    assert exporter.sync(box)["cloud_verified"]
    assert box.state(item.trace_id, exporter.target_id)["attempts"] == 2


def test_non_synthetic_records_stay_local_without_initializing_an_sdk_client(tmp_path, monkeypatch):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    box.append(record(synthetic=False))
    exporter = LangfuseExporter(config())
    def forbidden():
        pytest.fail("non-synthetic trace attempted a network/SDK operation")
    monkeypatch.setattr(exporter, "_client", forbidden)
    assert exporter.sync(box)["blocked_non_synthetic"] == 1
    assert not exporter.export_experiment(box, "synthetic-only")["cloud_verified"]


def test_original_timing_usage_and_cost_are_preserved_without_backdating_export_spans(tmp_path):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    item = record()
    box.append(item)
    client = FakeClient()
    assert LangfuseExporter(config(), client).sync(box)["cloud_verified"]
    generation = next(row for row in client.observations if row["type"] == "GENERATION")
    assert generation["metadata"]["original_elapsed_seconds"] == 0.3
    assert generation["metadata"]["model_executed_during_export"] is False
    assert generation["usage_details"] == {"input": 3, "output": 2}
    assert generation["cost_details"] is None


def test_provider_usage_aliases_do_not_double_the_langfuse_total(tmp_path):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    item = record(observations=[{"name": "embedding", "as_type": "generation", "model": "test-model",
                                "usage_details": {"prompt_tokens": 240, "total_tokens": 240}}])
    box.append(item)
    client = FakeClient()
    exporter = LangfuseExporter(config(), client)
    assert exporter.sync(box)["cloud_verified"]
    generation = next(row for row in client.observations if row["type"] == "GENERATION")
    assert generation["usage_details"] == {"input": 240, "total": 240}
    assert generation["metadata"]["original_usage_details"] == {"prompt_tokens": 240, "total_tokens": 240}
    generation["usage_details"] = {"prompt_tokens": 240, "total_tokens": 240, "total": 480}
    assert not exporter._verify_trace(item)


def test_usage_read_back_accepts_only_correct_service_derived_total():
    from repomind.platform.langfuse import _canonical_usage, _usage_matches
    assert _usage_matches({"input": 3, "output": 2, "total": 5}, {"prompt_tokens": 3, "completion_tokens": 2})
    assert not _usage_matches({"input": 3, "output": 2, "total": 10}, {"input": 3, "output": 2})
    assert not _usage_matches({"input": 3, "total": 6}, {"input": 3, "total": 3})
    with pytest.raises(ValueError, match="contradictory"):
        _canonical_usage({"input": 3, "prompt_tokens": 4})


def test_read_only_verification_never_reemits_missing_cloud_data(tmp_path):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    box.append(record())
    client = FakeClient()
    exporter = LangfuseExporter(config(), client)
    result = exporter.sync(box, verify_only=True)
    assert result["not_verified"] == 1 and not result["cloud_verified"]
    result = exporter.export_experiment(box, "test-dataset", verify_only=True)
    assert result["experiments"][0]["status"] == "not_verified"
    assert not any(name in {"start", "score", "flush"} for name, _ in client.calls)
    assert not client.dataset_calls and client.experiment_calls == 0
    assert exporter.sync(box)["cloud_verified"]
    emitted = len(client.observations)
    assert exporter.sync(box, verify_only=True)["cloud_verified"]
    assert len(client.observations) == emitted


def test_trace_sync_batches_flush_and_preserves_flush_failure(tmp_path):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    box.append(record())
    box.append(record(item_id="case-2"))
    client = FakeClient()
    assert LangfuseExporter(config(), client).sync(box)["cloud_verified"]
    assert sum(name == "flush" for name, _ in client.calls) == 1
    second = FakeClient()
    def failed_flush():
        raise OSError("synthetic flush failure")
    second.flush = failed_flush
    failed = LangfuseExporter(config(public_key="another-target"), second).sync(box)
    assert failed["failed"] == 2 and not failed["cloud_verified"]
    assert all(item["phase"] == "otel_flush" for item in failed["items"])


def test_developer_tasks_export_precomputed_experiments_without_model_rerun(tmp_path):
    box=TraceOutbox(tmp_path/'outbox.jsonl')
    box.append(record(stage='developer_task',input={'task':'change a sample function'},expected_output={'acceptance_test_count':4}))
    client=FakeClient()
    result=LangfuseExporter(config(),client).export_experiment(box,'developer-tasks')
    assert result['cloud_verified'] and client.experiment_calls==1
    assert result['stage_goal'].startswith('V2.0')


def test_modern_experiment_replays_precomputed_outputs_and_excludes_index_records(tmp_path, monkeypatch):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    box.append(record())
    box.append(record(provider="mem0"))
    box.append(record(stage="index", item_id="__index__:scope", output={"indexed": 3}, scores={}))
    client = FakeClient()
    exporter = LangfuseExporter(config(), client)
    result = exporter.export_experiment(box, "repo-evaluation", "release-run")
    assert result["cloud_verified"]
    assert len(result["experiments"]) == 2
    assert client.experiment_calls == 2
    assert len(client.experiment_items) == 2
    assert all(item["output"] == {"value": "MySQL"} for item in client.experiment_items)
    assert result["dataset_name"].startswith("repo-evaluation-")
    assert len({item["experiment_item_id"] for item in client.experiment_items}) == 1
    assert not result["model_executed_during_export"]
    assert not any(row["type"] == "GENERATION" or row["usage_details"] is not None for row in client.observations)
    exporter.export_experiment(box, "repo-evaluation", "release-run")
    assert client.experiment_calls == 2


def test_dataset_version_changes_with_input_and_provider_oracle_mismatch_is_rejected(tmp_path):
    exporter = LangfuseExporter(config(), FakeClient())
    first = TraceOutbox(tmp_path / "one.jsonl")
    first.append(record())
    first_result = exporter.export_experiment(first, "dataset")
    second = TraceOutbox(tmp_path / "two.jsonl")
    second.append(record(input={"question": "framework"}))
    second_result = exporter.export_experiment(second, "dataset")
    assert first_result["dataset_name"] != second_result["dataset_name"]
    mismatch = TraceOutbox(tmp_path / "mismatch.jsonl")
    mismatch.append(record())
    mismatch.append(record(provider="mem0", expected_output={"value": "Oracle"}))
    with pytest.raises(ValueError, match="disagree on input/gold"):
        exporter.export_experiment(mismatch, "dataset")


def _timestamp(nanoseconds):
    return datetime.fromtimestamp(nanoseconds / 1_000_000_000, timezone.utc).isoformat()


@contextmanager
def sdk_server():
    """A local protocol peer that materializes SDK OTLP and modern REST reads."""
    protobuf = pytest.importorskip("opentelemetry.proto.collector.trace.v1.trace_service_pb2")
    now = datetime.now(timezone.utc).isoformat()
    state = SimpleNamespace(requests=[], observations={}, scores={}, datasets={}, items={}, errors=[])

    def json_value(attributes, key, default=None):
        raw = attributes.get(key, default)
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except ValueError:
                pass
        return raw

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, value, *, protobuf_response=False, status=200):
            encoded = b"" if protobuf_response else json.dumps(value).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/x-protobuf" if protobuf_response else "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def do_POST(self):
            path = urlsplit(self.path).path
            state.requests.append(("POST", path))
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if self.headers.get("Content-Encoding") == "gzip":
                body = gzip.decompress(body)
            try:
                if path == "/api/public/otel/v1/traces":
                    message = protobuf.ExportTraceServiceRequest()
                    message.ParseFromString(body)
                    for resource in message.resource_spans:
                        for scope in resource.scope_spans:
                            for span in scope.spans:
                                attrs = {}
                                for attribute in span.attributes:
                                    value = attribute.value
                                    kind = value.WhichOneof("value")
                                    attrs[attribute.key] = getattr(value, kind)
                                metadata = {key.removeprefix("langfuse.observation.metadata."): json_value(attrs, key)
                                            for key in attrs if key.startswith("langfuse.observation.metadata.")}
                                observation = {"id": span.span_id.hex(), "traceId": span.trace_id.hex(),
                                    "startTime": _timestamp(span.start_time_unix_nano), "endTime": _timestamp(span.end_time_unix_nano),
                                    "projectId": "local-project", "name": span.name,
                                    "type": attrs.get("langfuse.observation.type", "span").upper(),
                                    "parentObservationId": span.parent_span_id.hex() or None,
                                    "level": "DEFAULT", "environment": "repomind-evaluation",
                                    "metadata": metadata, "input": json_value(attrs, "langfuse.observation.input"),
                                    "output": json_value(attrs, "langfuse.observation.output"),
                                    "model": attrs.get("langfuse.observation.model.name"),
                                    "usageDetails": json_value(attrs, "langfuse.observation.usage_details"),
                                    "costDetails": json_value(attrs, "langfuse.observation.cost_details"), "_attrs": attrs}
                                state.observations[observation["id"]] = observation
                    return self.respond({}, protobuf_response=True)
                payload = json.loads(body)
                if path == "/api/public/scores":
                    batch = payload if isinstance(payload, list) else payload.get("scores", [])
                    for score in batch:
                        identifier = score.get("id") or uuid.uuid4().hex
                        subject = ({"kind": "observation", "id": score["observationId"], "traceId": score.get("traceId")}
                                   if score.get("observationId") else {"kind": "trace", "id": score.get("traceId")})
                        state.scores[identifier] = {"id": identifier, "projectId": "local-project", "name": score["name"],
                            "value": score["value"], "dataType": score.get("dataType", "NUMERIC"), "source": "API",
                            "timestamp": score.get("timestamp", now), "environment": score.get("environment", "repomind-evaluation"),
                            "createdAt": now, "updatedAt": now, "metadata": score.get("metadata", {}), "subject": subject}
                    return self.respond({"accepted": len(batch)})
                if path == "/api/public/v2/datasets":
                    name = payload["name"]
                    state.datasets[name] = {**payload, "id": hashlib.sha256(name.encode()).hexdigest()[:16],
                                             "projectId": "local-project", "createdAt": now, "updatedAt": now}
                    return self.respond(state.datasets[name])
                if path == "/api/public/dataset-items":
                    dataset = state.datasets[payload["datasetName"]]
                    item = {**payload, "datasetId": dataset["id"], "status": "ACTIVE", "createdAt": now,
                            "updatedAt": now, "mediaReferences": []}
                    state.items[item["id"]] = item
                    return self.respond(item)
                raise ValueError("unexpected POST path " + path)
            except Exception as error:
                state.errors.append(type(error).__name__ + ": " + str(error))
                self.send_error(500, "local protocol test failure")

        def do_GET(self):
            parsed = urlsplit(self.path)
            path, params = parsed.path, parse_qs(parsed.query)
            state.requests.append(("GET", path))
            def param(name):
                return params.get(name, [None])[0]
            if path == "/api/public/projects":
                return self.respond({"data": [{"id": "local-project", "name": "Local contract", "metadata": {},
                                                "organization": {"id": "local-org", "name": "Synthetic tests"}}]})
            if path == "/api/public/v2/observations":
                if param("parseIoAsJson") == "true":
                    state.errors.append("deprecated parseIoAsJson=true causes HTTP 400")
                    return self.respond({"message": "parseIoAsJson=true is deprecated"}, status=400)
                rows = [{key: value for key, value in row.items() if not key.startswith("_")}
                        for row in state.observations.values() if row["traceId"] == param("traceId")]
                return self.respond({"data": rows, "meta": {}})
            if path == "/api/public/v3/scores":
                rows = [row for row in state.scores.values() if (row["subject"].get("traceId") or row["subject"]["id"]) == param("traceId")]
                return self.respond({"data": rows, "meta": {"limit": 100}})
            if path == "/api/public/experiment-items":
                rows = []
                for observation in state.observations.values():
                    attrs = observation["_attrs"]
                    if (attrs.get("langfuse.experiment.id") != param("experimentId")
                        or attrs.get("langfuse.experiment.item.root_observation_id") != observation["id"]):
                        continue
                    rows.append({"id": observation["id"], "traceId": observation["traceId"], "startTime": observation["startTime"],
                        "endTime": observation["endTime"], "level": "DEFAULT", "environment": "experiment",
                        "experimentId": attrs["langfuse.experiment.id"], "experimentName": attrs["langfuse.experiment.name"],
                        "experimentItemId": attrs["langfuse.experiment.item.id"], "input": observation["input"],
                        "output": observation["output"], "expectedOutput": json_value(attrs, "langfuse.experiment.item.expected_output"),
                        "metadata": observation["metadata"]})
                return self.respond({"data": rows, "meta": {}})
            state.errors.append("unexpected GET path " + path)
            self.send_error(404)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", state
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


def test_real_sdk5_uses_local_otel_and_modern_experiment_reads_without_legacy_ingestion(tmp_path, monkeypatch):
    langfuse = pytest.importorskip("langfuse")
    otel = pytest.importorskip("opentelemetry.sdk.trace")
    assert importlib.metadata.version("langfuse") == "5.0.4"
    monkeypatch.chdir(tmp_path)
    with sdk_server() as (url, state):
        settings = config(base_url=url, public_key="pk-lf-local-" + uuid.uuid4().hex, secret_key="sk-lf-local-test-secret")
        client = langfuse.Langfuse(public_key=settings.public_key.get_secret_value(), secret_key=settings.secret_key.get_secret_value(),
            base_url=url, timeout=3, sample_rate=1.0, debug=False, environment="repomind-evaluation",
            tracer_provider=otel.TracerProvider(), otel_compression="none")
        try:
            box = TraceOutbox(tmp_path / "real-sdk-outbox.jsonl")
            box.append(record())
            exporter = LangfuseExporter(settings, client, verify_attempts=2, verify_delay_seconds=0.01)
            sync = exporter.sync(box)
            assert not state.errors, state.errors
            assert sync["cloud_verified"], sync
            original_generations = sum(row["type"] == "GENERATION" for row in state.observations.values())
            experiment = exporter.export_experiment(box, "repo-local-contract", "contract-run")
            assert not state.errors, state.errors
            assert experiment["cloud_verified"], experiment
            assert ("POST", "/api/public/otel/v1/traces") in state.requests
            assert ("GET", "/api/public/v2/observations") in state.requests
            assert ("GET", "/api/public/v3/scores") in state.requests
            assert ("GET", "/api/public/experiment-items") in state.requests
            assert all("dataset-run-items" not in path and path != "/api/public/ingestion" for _, path in state.requests)
            assert any(row["type"] == "GENERATION" for row in state.observations.values())
            assert sum(row["type"] == "GENERATION" for row in state.observations.values()) == original_generations
        finally:
            client.shutdown()
