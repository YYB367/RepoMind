"""Local outbox integrity, credential removal, and explicit synthetic labels."""

import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from repomind.platform.tracing import TraceObservation, TraceOutbox, TraceRecord, clean_payload


def record(**changes):
    values = {"run_id": "run-1", "item_id": "case-1/query-1", "provider": "self", "project_id": "A",
              "stage": "query", "synthetic": True, "input": {"question": "database"},
              "output": {"status": "ok", "value": "MySQL"}, "scores": {"correct": 1.0},
              "observations": [{"name": "search", "elapsed_seconds": 0.03, "metadata": {"candidates": 3}}]}
    values.update(changes)
    return TraceRecord(**values)


def test_stable_trace_identity_and_payload_hash_do_not_depend_on_dict_order():
    left = record(metadata={"a": 1, "b": 2})
    right = record(metadata={"b": 2, "a": 1})
    assert left.trace_id == right.trace_id
    assert left.payload_sha256 == right.payload_sha256
    assert len(left.trace_id) == 32
    assert left.trace_id != record(provider="other").trace_id
    assert left.trace_id != record(project_id="B").trace_id
    assert left.trace_id != record(stage="index").trace_id


def test_outbox_reopens_and_same_id_same_payload_is_idempotent(tmp_path):
    path = tmp_path / "outbox.jsonl"
    box = TraceOutbox(path)
    item = record()
    assert box.append(item)
    assert not box.append(item)
    assert box.record(item) == item.trace_id
    assert TraceOutbox(path).records() == [item]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 1
    assert box.recorded_at(item.trace_id).tzinfo is not None


def test_same_identity_different_output_cannot_silently_overwrite(tmp_path):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    box.append(record())
    with pytest.raises(ValueError, match="different payload"):
        box.append(record(output={"status": "unknown"}))
    assert box.records() == [record()]


def test_known_credentials_are_removed_from_nested_payloads_and_receipts(tmp_path):
    secret = "sk-private-secret-that-must-not-leak"
    item = record(metadata={"api_key": secret, "Authorization": "Bearer " + secret,
                            "context.env": "TOKEN=" + secret, "context": {"env": {"x": secret}},
                            "note": "Bearer " + secret, "tokens": {"input_tokens": 4}, "cost_usd": None},
                  input={"query": "database", "child": [{"embedding_api_key": secret}]})
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    box.append(item)
    box.record_status(item.trace_id, "failed", {"secret_key": secret, "diagnostic": "local synthetic failure"})
    raw = box.path.read_text(encoding="utf-8") + box.receipts_path.read_text(encoding="utf-8")
    assert secret not in raw
    assert "api_key" not in raw
    assert "Authorization" not in raw
    assert "context.env" not in raw
    assert item.metadata["tokens"] == {"input_tokens": 4}
    assert item.metadata["cost_usd"] is None


@pytest.mark.parametrize("changes", [
    {"input": float("nan")}, {"output": float("inf")}, {"scores": {"correct": True}},
    {"scores": {"latency": float("nan")}}, {"metadata": {"input_tokens": True}},
    {"metadata": {"cost_usd": -0.01}}, {"scores": {"x": 10 ** 1000}},
    {"run_id": "sk-private-secret-123456"}, {"scores": {"api_key": 1.0}},
])
def test_nonfinite_unmeasured_or_credential_shaped_fields_are_rejected(changes):
    with pytest.raises(ValueError):
        record(**changes)


def test_validation_errors_do_not_echo_other_secret_input_fields():
    with pytest.raises(ValueError) as raised:
        record(metadata={"api_key": "super-private-value", "cost_usd": float("nan")})
    assert "super-private-value" not in str(raised.value)


def test_synthetic_flag_is_required_and_false_is_kept_locally(tmp_path):
    values = record().model_dump()
    del values["synthetic"]
    with pytest.raises(ValueError):
        TraceRecord.model_validate(values)
    with pytest.raises(ValueError):
        record(synthetic=1)
    item = record(synthetic=False)
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    assert box.append(item)
    assert box.records()[0].synthetic is False


def test_minimal_observation_has_unknown_cost_and_usage_without_fake_zeroes():
    item = TraceObservation(name="resolve", elapsed_seconds=0.2, metadata={})
    assert item.as_type == "span"
    assert item.usage_details is item.cost_details is None
    assert TraceObservation(name="unmeasured").elapsed_seconds is None
    with pytest.raises(ValueError):
        TraceObservation(name="generation", usage_details={"input": True})
    with pytest.raises(ValueError):
        TraceObservation(name="generation", cost_details={"total": float("inf")})


def test_receipt_state_attempts_are_target_specific_and_survive_restart(tmp_path):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    item = record()
    box.append(item)
    box.record_status(item.trace_id, "sent_unconfirmed", target="project-one")
    box.record_status(item.trace_id, "failed", target="project-one")
    assert box.state(item.trace_id, "project-one")["attempts"] == 1
    box.record_status(item.trace_id, "sent_unconfirmed", target="project-one")
    box.record_status(item.trace_id, "verified", target="project-one")
    reopened = TraceOutbox(box.path)
    assert reopened.state(item.trace_id, "project-one")["status"] == "verified"
    assert reopened.state(item.trace_id, "project-one")["attempts"] == 2
    assert reopened.pending("project-one") == []
    assert reopened.pending("different-project") == [item]
    with pytest.raises(ValueError, match="absent"):
        box.record_status("missing", "verified")


def test_torn_or_tampered_jsonl_is_reported_without_truncating_user_files(tmp_path):
    path = tmp_path / "outbox.jsonl"
    box = TraceOutbox(path)
    box.append(record())
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw + '{"torn":', encoding="utf-8")
    with pytest.raises(ValueError, match="invalid/torn"):
        box.records()
    assert path.read_text(encoding="utf-8") == raw + '{"torn":'
    wrapper = json.loads(raw)
    wrapper["payload_sha256"] = "0" * 64
    path.write_text(json.dumps(wrapper) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="hash mismatch"):
        box.records()


def test_one_instance_serializes_threads_without_duplicate_records(tmp_path):
    box = TraceOutbox(tmp_path / "outbox.jsonl")
    with ThreadPoolExecutor(max_workers=4) as workers:
        values = list(workers.map(lambda _: box.append(record()), range(16)))
    assert sum(values) == 1
    assert len(box.records()) == 1
