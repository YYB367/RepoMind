"""Explicit Langfuse SDK 5 export of precomputed synthetic benchmark records.

Importing or constructing this adapter neither loads .env nor contacts a server.
Flush is not an acknowledgement: delivery is verified through modern read APIs.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.metadata
import json
import os
import re
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from repomind.domain.models import Text
from repomind.intelligence.providers import ProviderConfig
from repomind.platform.tracing import TraceOutbox, TraceRecord, canonical_json, clean_payload


class LangfuseConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    base_url: Text
    public_key: SecretStr = Field(repr=False, exclude=True)
    secret_key: SecretStr = Field(repr=False, exclude=True)
    timeout_seconds: int = Field(default=10, ge=1, le=60, strict=True)
    environment: Text = "repomind-evaluation"

    @field_validator("base_url")
    @classmethod
    def safe_endpoint(cls, value: str) -> str:
        return ProviderConfig.safe_endpoint(value)

    @field_validator("public_key", "secret_key")
    @classmethod
    def nonempty_keys(cls, value: SecretStr) -> SecretStr:
        text = value.get_secret_value()
        if not text or any(ord(character) <= 32 or ord(character) > 126 for character in text):
            raise ValueError("Langfuse credentials must be nonempty ASCII tokens")
        return value

    @classmethod
    def from_env(cls) -> "LangfuseConfig":
        """Read already-loaded environment variables, never a local .env file."""
        return cls(base_url=os.getenv("LANGFUSE_BASE_URL", ""),
                   public_key=os.getenv("LANGFUSE_PUBLIC_KEY", ""),
                   secret_key=os.getenv("LANGFUSE_SECRET_KEY", ""))

    @property
    def target_id(self) -> str:
        identity = {"base_url": self.base_url,
                    "public_key_sha256": hashlib.sha256(self.public_key.get_secret_value().encode()).hexdigest()}
        return "langfuse:" + hashlib.sha256(canonical_json(identity).encode()).hexdigest()[:32]

    def safe_metadata(self) -> dict[str, Any]:
        return {**self.model_dump(mode="json"), "target_id": self.target_id, "credentials_configured": True,
                "sdk_contract": "langfuse==5.0.4"}


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return value
    if hasattr(value, "__dict__"):
        return vars(value)
    return value


def _field(value: Any, name: str, *aliases: str, default: Any = None) -> Any:
    data = _plain(value)
    if isinstance(data, dict):
        for key in (name, *aliases):
            if key in data:
                return data[key]
    return default


def _metadata_value(metadata: dict[str, Any], key: str) -> Any:
    value = metadata.get(key)
    if isinstance(value, str) and value.startswith('"'):
        try:
            return json.loads(value)
        except ValueError:
            pass
    return value


def _same_json(left: Any, right: Any) -> bool:
    if isinstance(left, str) and not isinstance(right, str):
        try:
            left = json.loads(left)
        except ValueError:
            return False
    try:
        return canonical_json(left) == canonical_json(right)
    except (TypeError, ValueError):
        return False


def _canonical_usage(usage: dict[str, int] | None) -> dict[str, int] | None:
    """Langfuse sums unrecognized counters; never send total_tokens twice.

    Preserve raw provider counters in metadata. Map only documented aliases,
    reject contradictory aliases, and keep missing usage unknown.
    """
    if usage is None:
        return None
    groups = {"input": ("input", "input_tokens", "prompt_tokens"),
              "output": ("output", "output_tokens", "completion_tokens"),
              "total": ("total", "total_tokens")}
    aliases = {alias for group in groups.values() for alias in group}
    result = {key: value for key, value in usage.items() if key not in aliases}
    for target, names in groups.items():
        values = [usage[name] for name in names if name in usage]
        if values:
            if len(set(values)) != 1:
                raise ValueError("contradictory token usage aliases")
            result[target] = values[0]
    return result


def _usage_matches(actual: Any, original: dict[str, int]) -> bool:
    expected = _canonical_usage(original)
    if not isinstance(actual, dict) or any(actual.get(key) != value for key, value in expected.items()):
        return False
    extras = set(actual) - set(expected)
    if not extras:
        return True
    # The service may derive a total from supplied component counters.
    return extras == {"total"} and actual["total"] == sum(expected.values())


def _safe_error(error: Exception) -> dict[str, Any]:
    kind = type(error).__name__
    details = {"error_type": kind if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,80}", kind) else "ExportError",
               "message": "Langfuse export/read-back failed; sensitive upstream text omitted"}
    code = getattr(error, "status_code", None)
    if type(code) is int and 100 <= code <= 599:
        details["http_status"] = code
    return details


class LangfuseExporter:
    def __init__(self, config: LangfuseConfig, client: Any = None, *, verify_attempts: int = 1,
                 verify_delay_seconds: float = 0.25):
        if type(verify_attempts) is not int or not 1 <= verify_attempts <= 10:
            raise ValueError("verify_attempts must be between 1 and 10")
        if type(verify_delay_seconds) not in (int, float) or not 0 <= verify_delay_seconds <= 5:
            raise ValueError("verify_delay_seconds must be between 0 and 5")
        self.config = LangfuseConfig.model_validate(config.model_dump() | {"public_key": config.public_key, "secret_key": config.secret_key})
        self.client = client
        self.verify_attempts = verify_attempts
        self.verify_delay_seconds = verify_delay_seconds
        self._closed = False

    def close(self) -> None:
        """Stop only an existing SDK client; never construct one to close it."""
        if self._closed:
            return
        self._closed = True
        shutdown = getattr(self.client, "shutdown", None) if self.client is not None else None
        if callable(shutdown):
            shutdown()

    @property
    def target_id(self) -> str:
        return self.config.target_id

    def _client(self) -> Any:
        if self._closed:
            raise ValueError("Langfuse exporter is already closed")
        if self.client is None:
            try:
                version = importlib.metadata.version("langfuse")
                if version.split(".", 1)[0] != "5":
                    raise ValueError("Langfuse export requires optional Python SDK major 5")
                from langfuse import Langfuse
            except importlib.metadata.PackageNotFoundError:
                raise ValueError("install the optional Langfuse SDK 5 dependency before explicit export") from None
            self.client = Langfuse(public_key=self.config.public_key.get_secret_value(),
                                   secret_key=self.config.secret_key.get_secret_value(),
                                   base_url=self.config.base_url, timeout=self.config.timeout_seconds,
                                   environment=self.config.environment, sample_rate=1.0, debug=False)
        return self.client

    @staticmethod
    def _record_metadata(record: TraceRecord) -> dict[str, Any]:
        return {**record.metadata, "repomind_record_sha256": record.payload_sha256,
                "repomind_local_trace_id": record.trace_id, "repomind_run_id": record.run_id,
                "repomind_item_id": record.item_id, "repomind_provider": record.provider,
                "repomind_project_id": record.project_id, "synthetic": True,
                "replayed_export": True, "model_executed_during_export": False,
                "timing_policy": "cloud spans measure export replay; original_* metadata retains original run timing"}

    def _children(self, record: TraceRecord, parent: Any = None, *, replay_only: bool = False) -> None:
        client = self._client()
        for index, observation in enumerate(record.observations):
            metadata = {**observation.metadata, **self._record_metadata(record),
                        "repomind_observation_key": f"step-{index:04d}"}
            if observation.elapsed_seconds is not None:
                metadata["original_elapsed_seconds"] = observation.elapsed_seconds
            if observation.started_at is not None:
                metadata["original_started_at"] = observation.started_at.isoformat()
            if observation.ended_at is not None:
                metadata["original_ended_at"] = observation.ended_at.isoformat()
            if observation.usage_details is not None:
                metadata["original_usage_details"] = observation.usage_details
            if replay_only:
                metadata.update(original_as_type=observation.as_type, original_model=observation.model,
                                original_usage_details=observation.usage_details, original_cost_details=observation.cost_details)
            arguments = {"name": observation.name, "as_type": "span" if replay_only else observation.as_type,
                         "input": observation.input, "output": observation.output, "metadata": metadata}
            if observation.as_type == "generation" and not replay_only:
                arguments.update(model=observation.model, usage_details=_canonical_usage(observation.usage_details),
                                 cost_details=observation.cost_details)
            owner = parent if parent is not None else client
            with owner.start_as_current_observation(**arguments):
                pass

    @staticmethod
    def _score_id(record: TraceRecord, name: str) -> str:
        return hashlib.sha256((record.trace_id + "/score/" + name).encode()).hexdigest()[:32]

    def _emit_trace(self, record: TraceRecord, *, score_timestamp: datetime | None = None) -> None:
        client = self._client()
        metadata = {**self._record_metadata(record), "repomind_observation_key": "root"}
        with client.start_as_current_observation(name="repomind:" + record.stage, as_type="span",
                                                trace_context={"trace_id": record.trace_id},
                                                input=record.input, output=record.output, metadata=metadata) as span:
            self._children(record, span)
        for name, value in record.scores.items():
            client.create_score(trace_id=record.trace_id, score_id=self._score_id(record, name),
                                name=name, value=value, data_type="NUMERIC",
                                timestamp=score_timestamp,
                                metadata={"repomind_record_sha256": record.payload_sha256, "precomputed": True})

    @staticmethod
    def _pages(method: Any, **kwargs: Any) -> list[Any]:
        rows, cursor, seen = [], None, set()
        for _ in range(20):
            request = {**kwargs, "limit": 100}
            if cursor is not None:
                request["cursor"] = cursor
            response = method(**request)
            data = _field(response, "data")
            if not isinstance(data, list):
                raise ValueError("Langfuse read API returned no data array")
            rows.extend(data)
            cursor = _field(_field(response, "meta", default={}), "cursor")
            if not cursor:
                return rows
            if cursor in seen:
                raise ValueError("Langfuse read API repeated a pagination cursor")
            seen.add(cursor)
        raise ValueError("Langfuse read-back exceeded its page limit")

    def _scores_match(self, record: TraceRecord, trace_id: str, *, deterministic_ids: bool) -> bool:
        if not record.scores:
            return True
        scores = self._pages(self._client().api.scores.get_many, trace_id=trace_id, fields="subject,details")
        for name, value in record.scores.items():
            matched = False
            for score in scores:
                metadata = _field(score, "metadata", default={}) or {}
                subject = _field(score, "subject", default={}) or {}
                subject_matches = ((_field(subject, "kind") == "trace" and _field(subject, "id") == trace_id)
                                   or (_field(subject, "kind") == "observation" and _field(subject, "trace_id", "traceId") == trace_id))
                if (_field(score, "name") == name and _field(score, "value") == value
                    and _field(score, "data_type", "dataType", default="NUMERIC") == "NUMERIC"
                    and _metadata_value(metadata, "repomind_record_sha256") == record.payload_sha256
                    and subject_matches
                    and (not deterministic_ids or _field(score, "id") == self._score_id(record, name))):
                    matched = True
                    break
            if not matched:
                return False
        return True

    def _verify_trace(self, record: TraceRecord) -> bool:
        rows = self._pages(self._client().api.observations.get_many, trace_id=record.trace_id,
                           fields="core,basic,io,metadata,model,usage")
        expected = {"root": ("SPAN", record.input, record.output, None)}
        for index, observation in enumerate(record.observations):
            expected[f"step-{index:04d}"] = (observation.as_type.upper(), observation.input, observation.output, observation)
        found = set()
        for row in rows:
            if _field(row, "trace_id", "traceId") != record.trace_id:
                continue
            metadata = _field(row, "metadata", default={}) or {}
            if not isinstance(metadata, dict) or _metadata_value(metadata, "repomind_record_sha256") != record.payload_sha256:
                continue
            key = _metadata_value(metadata, "repomind_observation_key")
            if key not in expected:
                continue
            kind, input_value, output_value, observation = expected[key]
            if (_field(row, "type") != kind or not _same_json(_field(row, "input"), input_value)
                or not _same_json(_field(row, "output"), output_value)):
                continue
            if observation is not None:
                if observation.elapsed_seconds is not None and _metadata_value(metadata, "original_elapsed_seconds") != observation.elapsed_seconds:
                    continue
                if observation.as_type == "generation":
                    if observation.model is not None and _field(row, "model") != observation.model:
                        continue
                    if observation.usage_details is not None and not _usage_matches(_field(row, "usage_details", "usageDetails"), observation.usage_details):
                        continue
                    if observation.cost_details is not None and not _same_json(_field(row, "cost_details", "costDetails"), observation.cost_details):
                        continue
            found.add(key)
        return set(expected).issubset(found) and self._scores_match(record, record.trace_id, deterministic_ids=True)

    def _poll(self, check: Any) -> bool:
        for index in range(self.verify_attempts):
            if check():
                return True
            if index + 1 < self.verify_attempts and self.verify_delay_seconds:
                time.sleep(self.verify_delay_seconds)
        return False

    def sync(self, outbox: TraceOutbox, *, verify_only: bool = False) -> dict[str, Any]:
        records = outbox.records()
        items = []
        queued = []
        for record in records:
            if not record.synthetic:
                items.append({"trace_id": record.trace_id, "status": "blocked_non_synthetic", "network_called": False})
                continue
            state = outbox.state(record.trace_id, self.target_id)
            phase = "preflight_read"
            try:
                if self._verify_trace(record):
                    outbox.record_status(record.trace_id, "verified", {"recovered_by_read_back": True,
                                         "previously_verified": state["status"] == "verified"}, target=self.target_id)
                elif verify_only:
                    items.append({"trace_id": record.trace_id, "status": "not_verified", "network_write_called": False})
                    continue
                else:
                    phase = "otel_export"
                    self._emit_trace(record, score_timestamp=outbox.recorded_at(record.trace_id))
                    item = {"trace_id": record.trace_id, "status": "queued", "skipped_verified": False}
                    items.append(item)
                    queued.append((record, item))
                    continue
                current = outbox.state(record.trace_id, self.target_id)
                items.append({"trace_id": record.trace_id, "status": current["status"], "attempts": current["attempts"],
                              "skipped_verified": state["status"] == "verified" and current["status"] == "verified"})
            except Exception as error:
                details = {"phase": phase, **_safe_error(error)}
                outbox.record_status(record.trace_id, "failed", details, target=self.target_id)
                items.append({"trace_id": record.trace_id, "status": "failed", **details})
        # Let the SDK batch OTEL observations/scores, then verify separately.
        # Per-record flush + immediate repeated reads amplified network latency
        # without making the asynchronous service visible any sooner.
        if queued:
            flush_error = None
            try:
                self._client().flush()
            except Exception as error:
                flush_error = {"phase": "otel_flush", **_safe_error(error)}
            for record, item in queued:
                try:
                    if flush_error:
                        outbox.record_status(record.trace_id, "failed", flush_error, target=self.target_id)
                        item.update(status="failed", **flush_error)
                        continue
                    outbox.record_status(record.trace_id, "sent_unconfirmed", {"flush_returned": True}, target=self.target_id)
                    if self._poll(lambda: self._verify_trace(record)):
                        outbox.record_status(record.trace_id, "verified", {"read_back_confirmed": True}, target=self.target_id)
                    current = outbox.state(record.trace_id, self.target_id)
                    item.update(status=current["status"], attempts=current["attempts"])
                except Exception as error:
                    details = {"phase": "read_back", **_safe_error(error)}
                    outbox.record_status(record.trace_id, "failed", details, target=self.target_id)
                    item.update(status="failed", **details)
        counts = {status: sum(item["status"] == status for item in items)
                  for status in ("verified", "sent_unconfirmed", "failed", "blocked_non_synthetic", "not_verified")}
        export_stage="V2.0" if any(record.stage=="developer_task" for record in records) else "V1.2"
        return {"stage_goal": export_stage+"：显式同步合成评测 trace，服务读回后确认交付",
                "target_id": self.target_id, "status": "verified" if items and counts["verified"] == len(items) else "partial",
                "cloud_verified": bool(items) and counts["verified"] == len(items), **counts,
                "verify_only": verify_only,
                "exported": counts["verified"], "items": items,
                "delivery_semantics": "at-least-once; stable trace IDs and local ACKs do not promise exactly-once spans"}

    @staticmethod
    def _dataset_plan(records: list[TraceRecord], prefix: str) -> tuple[str, dict[tuple[str, str], str]]:
        if not isinstance(prefix, str) or not prefix.strip() or clean_payload(prefix) != prefix:
            raise ValueError("dataset_name must be a nonempty label without credentials")
        contents = {}
        for record in records:
            key = record.project_id, record.item_id
            payload = {"project_id": record.project_id, "item_id": record.item_id,
                       "input": record.input, "expected_output": record.expected_output}
            if key in contents and contents[key] != payload:
                raise ValueError("providers disagree on input/gold for one dataset item")
            contents[key] = payload
        version = hashlib.sha256(canonical_json([contents[key] for key in sorted(contents)]).encode()).hexdigest()
        name = prefix.strip() + "-" + version[:12]
        ids = {key: hashlib.sha256((name + "/" + canonical_json(payload)).encode()).hexdigest()[:32]
               for key, payload in contents.items()}
        return name, ids

    def _verify_experiment(self, records: list[TraceRecord], experiment_id: str,
                           item_ids: dict[tuple[str, str], str], since: datetime) -> bool:
        rows = self._pages(self._client().api.experiments.list_items, experiment_id=experiment_id,
                           from_start_time=since, fields="core,io,itemMetadata,metadata")
        for record in records:
            wanted_id = item_ids[(record.project_id, record.item_id)]
            matches = [row for row in rows if _field(row, "experiment_id", "experimentId") == experiment_id
                       and _field(row, "experiment_item_id", "experimentItemId") == wanted_id]
            matched = False
            for row in matches:
                metadata = _field(row, "metadata", default={}) or {}
                if (_metadata_value(metadata, "repomind_record_sha256") != record.payload_sha256
                    or not _same_json(_field(row, "input"), {"project_id": record.project_id, "item_id": record.item_id, "query": record.input})
                    or not _same_json(_field(row, "output"), record.output)
                    or not _same_json(_field(row, "expected_output", "expectedOutput"), record.expected_output)):
                    continue
                trace_id = _field(row, "trace_id", "traceId")
                if isinstance(trace_id, str) and self._scores_match(record, trace_id, deterministic_ids=False):
                    matched = True
                    break
            if not matched:
                return False
        return True

    def export_experiment(self, outbox: TraceOutbox, dataset_name: str, run_name: str | None = None, *, verify_only: bool = False) -> dict[str, Any]:
        all_records = [record for record in outbox.records() if record.stage in {"query", "developer_task"}]
        blocked = [record.trace_id for record in all_records if not record.synthetic]
        records = [record for record in all_records if record.synthetic]
        if not records:
            return {"status": "partial", "cloud_verified": False, "experiments": [], "blocked_non_synthetic": blocked,
                    "reason": "no explicitly synthetic stage=query records; index stages are not dataset items"}
        if run_name is not None and (not run_name.strip() or clean_payload(run_name) != run_name):
            raise ValueError("run_name must not be empty or contain credentials")
        effective_dataset, item_ids = self._dataset_plan(records, dataset_name)
        groups: dict[tuple[str, str], list[TraceRecord]] = defaultdict(list)
        for record in records:
            groups[(record.run_id, record.provider)].append(record)
        results = []
        for (run_id, provider), group in sorted(groups.items()):
            group.sort(key=lambda record: (record.project_id, record.item_id))
            experiment_id = hashlib.sha256(canonical_json([run_id, provider, effective_dataset]).encode()).hexdigest()[:32]
            target = self.target_id + ":experiment:" + experiment_id
            name = (run_name or "RepoMind/" + run_id) + "/" + provider
            previously_verified = all(outbox.state(record.trace_id, target)["status"] == "verified" for record in group)
            # The journal's earliest local record time precedes any possible
            # export; using it also recovers acknowledgements after a restart.
            since = min(outbox.recorded_at(record.trace_id) for record in group) - timedelta(days=1)
            phase = "preflight_read"
            try:
                if not self._verify_experiment(group, experiment_id, item_ids, since):
                    if verify_only:
                        results.append({"provider": provider, "experiment_id": experiment_id,
                                        "target_id": target, "status": "not_verified", "network_write_called": False})
                        continue
                    client = self._client()
                    phase = "dataset_upsert"
                    dataset = client.create_dataset(name=effective_dataset,
                        description="Explicitly exported synthetic RepoMind benchmark; precomputed replay only",
                        metadata={"synthetic": True, "dataset_identity": effective_dataset})
                    remote_items, by_item = [], {}
                    for record in group:
                        item_id = item_ids[(record.project_id, record.item_id)]
                        item = client.create_dataset_item(dataset_name=effective_dataset, id=item_id,
                            input={"project_id": record.project_id, "item_id": record.item_id, "query": record.input},
                            expected_output=record.expected_output,
                            metadata={"synthetic": True, "repomind_item_id": record.item_id,
                                      "repomind_project_id": record.project_id})
                        if _field(item, "id") != item_id or _field(item, "dataset_id", "datasetId") != _field(dataset, "id"):
                            raise ValueError("dataset API returned a different dataset/item identity")
                        remote_items.append(item)
                        by_item[item_id] = record

                    def cached_task(*, item: Any, **kwargs: Any) -> Any:
                        record = by_item[_field(item, "id")]
                        # Runs inside the SDK experiment-item-task observation.
                        client.update_current_span(metadata=self._record_metadata(record))
                        self._children(record, replay_only=True)
                        return record.output

                    def cached_scores(*, metadata: Any, **kwargs: Any) -> list[dict[str, Any]]:
                        item_id = _field(metadata, "repomind_item_id")
                        project_id = _field(metadata, "repomind_project_id")
                        matches = [record for record in group if (record.project_id, record.item_id) == (project_id, item_id)]
                        if len(matches) != 1:
                            raise ValueError("experiment evaluator cannot identify one precomputed item")
                        record = matches[0]
                        return [{"name": score, "value": value, "data_type": "NUMERIC",
                                 "metadata": {"repomind_record_sha256": record.payload_sha256, "precomputed": True}}
                                for score, value in record.scores.items()]

                    phase = "experiment_replay"
                    experiment = client.run_experiment(name="RepoMind synthetic comparison", run_name=name,
                        experiment_id=experiment_id, data=remote_items, task=cached_task, evaluators=[cached_scores],
                        max_concurrency=1, metadata={"synthetic": "true", "provider": provider,
                                                   "source_run_id": run_id, "model_executed_during_export": "false"})
                    if len(experiment.item_results) != len(group):
                        raise ValueError("SDK experiment did not return every precomputed item")
                    client.flush()
                    for record in group:
                        outbox.record_status(record.trace_id, "sent_unconfirmed", {"flush_returned": True,
                                              "experiment_id": experiment_id}, target=target)
                    phase = "read_back"
                    if not self._poll(lambda: self._verify_experiment(group, experiment_id, item_ids, since)):
                        results.append({"provider": provider, "experiment_id": experiment_id, "target_id": target,
                                        "status": "sent_unconfirmed"})
                        continue
                for record in group:
                    outbox.record_status(record.trace_id, "verified", {"read_back_confirmed": True,
                                          "experiment_id": experiment_id}, target=target)
                results.append({"provider": provider, "experiment_id": experiment_id, "target_id": target,
                                "status": "verified", "skipped_verified": previously_verified})
            except Exception as error:
                details = {"phase": phase, **_safe_error(error)}
                for record in group:
                    outbox.record_status(record.trace_id, "failed", details, target=target)
                results.append({"provider": provider, "experiment_id": experiment_id, "target_id": target,
                                "status": "failed", **details})
        verified = bool(results) and not blocked and all(result["status"] == "verified" for result in results)
        export_stage="V2.0" if any(record.stage=="developer_task" for record in records) else "V1.2"
        return {"stage_goal": export_stage+"：将预计算合成结果导出为现代 Langfuse SDK experiment，避免重跑模型",
                "target_id": self.target_id, "dataset_name": effective_dataset, "dataset_prefix": dataset_name,
                "status": "verified" if verified else "partial", "cloud_verified": verified,
                "blocked_non_synthetic": blocked, "experiments": results,
                "model_executed_during_export": False,
                "verify_only": verify_only,
                "delivery_semantics": "at-least-once; interrupted replays can create duplicate observation IDs"}
