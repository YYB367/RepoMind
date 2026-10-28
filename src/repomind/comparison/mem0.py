"""Mem0 OSS 2.2.1 controlled retrieval through its public OpenAI boundary.

This is not a comparison of Mem0's extraction, conflict handling or temporal
inference. Raw property documents use ``infer=False``; only returned keys reach
the common V1 resolver. Optional NLP/BM25 packages are deliberately absent in
this reproducible profile, avoiding SDK-triggered model downloads.
"""

from contextlib import contextmanager
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import importlib.metadata
import importlib.util
import json
import math
from numbers import Real
import os
from pathlib import Path
import secrets
import sys
import threading
import time
from typing import Any

from repomind.comparison.base import ScopeViolationError, ScopedReadout, embedding_metadata, request, scope
from repomind.domain.models import MemoryQuery
from repomind.intelligence.search import SearchIndexError, build_documents, validate_vector
from repomind.memory.retriever import MemoryRetriever


SUPPORTED_MEM0_VERSION = "2.2.1"
_IMPORT_LOCK = threading.Lock()


class MemoryBackendError(ValueError):
    """The real SDK failed; no native backend fallback was substituted."""


def _digest(value: object) -> str:
    content = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@contextmanager
def _safe_sdk_environment(directory: Path):
    """Initialize SDK globals safely and keep its HTTP clients on loopback."""
    values = {"MEM0_DIR": str(directory), "MEM0_TELEMETRY": "False"}
    previous = {name: os.environ.get(name) for name in (*values, "NO_PROXY", "no_proxy")}
    bypass = ",".join(filter(None, [previous["NO_PROXY"] or previous["no_proxy"], "127.0.0.1,localhost,::1"]))
    values.update({"NO_PROXY": bypass, "no_proxy": bypass})
    try:
        os.environ.update(values)
        yield
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value


def _memory_class(directory: Path):
    with _IMPORT_LOCK, _safe_sdk_environment(directory):
        existing = sys.modules.get("mem0.memory.setup")
        telemetry = sys.modules.get("mem0.memory.telemetry")
        if existing is not None:
            actual = Path(existing.mem0_dir).resolve()
            if actual == (Path.home() / ".mem0").resolve() or (telemetry is not None and telemetry.MEM0_TELEMETRY):
                raise MemoryBackendError("Mem0 was already imported with unsafe HOME/telemetry defaults; use a fresh process")
        from mem0 import Memory
        from mem0.memory import setup, telemetry as telemetry_module
        if telemetry_module.MEM0_TELEMETRY:
            raise MemoryBackendError("Mem0 telemetry must be disabled before its first import")
        return Memory, str(Path(setup.mem0_dir).resolve())


class _EmbeddingBridge:
    """SDK's local OpenAI endpoint; the real provider key never enters Mem0."""

    def __init__(self, embedder, model: str, dimension: int):
        self.embedder, self.model, self.dimension = embedder, model, dimension
        self.key = secrets.token_urlsafe(32)
        self.operation = None
        self.prepared_documents: dict[str, list[float]] = {}
        self.requests = self.embedding_requests = self.llm_attempts = self.rejections = 0
        self.upstream_calls = self.prepared_hits = 0
        self.elapsed_seconds = 0.0
        self.last_error_type = None
        self.input_digests: list[dict[str, Any]] = []
        self._counter_lock, self._upstream_lock = threading.Lock(), threading.Lock()
        bridge = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def reply(self, status: int, body: dict):
                encoded = json.dumps(body, ensure_ascii=False, allow_nan=False).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(encoded)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                self.wfile.write(encoded)

            def do_POST(self):
                started = time.perf_counter()
                with bridge._counter_lock:
                    bridge.requests += 1
                try:
                    auth = self.headers.get("Authorization", "")
                    if not hmac.compare_digest(auth, "Bearer " + bridge.key):
                        raise ValueError("bridge authorization rejected")
                    if self.path != "/v1/embeddings":
                        if "completions" in self.path:
                            bridge.llm_attempts += 1
                        raise ValueError("bridge allows embeddings only")
                    length = int(self.headers.get("Content-Length", "0"))
                    if not 0 < length <= 2_000_000:
                        raise ValueError("bridge request size invalid")
                    payload = json.loads(self.rfile.read(length).decode("utf-8"))
                    if not isinstance(payload, dict) or payload.get("model") != bridge.model:
                        raise ValueError("bridge model differs from configured model")
                    if payload.get("dimensions", bridge.dimension) != bridge.dimension:
                        raise ValueError("bridge dimension differs from configured dimension")
                    texts = payload.get("input")
                    if not isinstance(texts, list) or not texts or any(not isinstance(text, str) or not text.strip() for text in texts):
                        raise ValueError("bridge inputs must be nonempty strings")
                    if bridge.operation not in {"document", "query"}:
                        raise ValueError("bridge has no active scoped operation")
                    with bridge._upstream_lock:
                        bridge.embedding_requests += 1
                        bridge.input_digests.append({
                            "operation": bridge.operation,
                            "text_sha256": [hashlib.sha256(text.encode("utf-8")).hexdigest() for text in texts],
                        })
                        if bridge.operation == "document" and len(texts) == 1 and texts[0] in bridge.prepared_documents:
                            returned = [bridge.prepared_documents.pop(texts[0])]
                            bridge.prepared_hits += 1
                        elif bridge.operation == "query" and callable(getattr(bridge.embedder, "embed_query", None)):
                            bridge.upstream_calls += len(texts)
                            returned = [bridge.embedder.embed_query(text) for text in texts]
                        else:
                            bridge.upstream_calls += 1
                            returned = bridge.embedder.embed(texts)
                    if not isinstance(returned, list) or len(returned) != len(texts):
                        raise ValueError("bridge embedding count invalid")
                    vectors = [validate_vector(item, context="bridge embedding") for item in returned]
                    if any(len(vector) != bridge.dimension for vector in vectors):
                        raise ValueError("bridge vector dimension changed")
                    self.reply(200, {"object": "list", "model": bridge.model, "data": [
                        {"object": "embedding", "index": index, "embedding": vector}
                        for index, vector in enumerate(vectors)
                    ]})
                except Exception as exc:
                    bridge.last_error_type = type(exc).__name__
                    bridge.rejections += 1
                    # A 400 prevents OpenAI SDK's default 5xx retry policy from
                    # repeating actual upstream requests. Do not echo error text.
                    try:
                        self.reply(400, {"error": {"message": "controlled embedding bridge rejected request"}})
                    except (BrokenPipeError, ConnectionResetError, OSError):
                        pass
                finally:
                    bridge.elapsed_seconds += time.perf_counter() - started

            def do_GET(self):
                bridge.rejections += 1
                self.reply(400, {"error": {"message": "controlled embedding bridge requires POST"}})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"
        self.worker = threading.Thread(target=lambda: self.server.serve_forever(poll_interval=0.01), daemon=True)
        self.worker.start()

    def metadata(self) -> dict[str, Any]:
        return {"transport": "loopback OpenAI HTTP bridge", "requests": self.requests,
                "embedding_requests": self.embedding_requests, "llm_attempts": self.llm_attempts,
                "rejected_requests": self.rejections, "upstream_invocations": self.upstream_calls,
                "dimension_probe_reuse": self.prepared_hits, "elapsed_seconds": self.elapsed_seconds,
                "input_digests": list(self.input_digests), "last_error_type": self.last_error_type,
                "retry_policy": "upstream errors become local HTTP400; no remote retry or fallback"}

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=2)


class Mem0MemoryProvider:
    name = "mem0"

    def __init__(self, store, embedder, state_dir: Path, run_id: str):
        self.store, self.embedder = ScopedReadout(store, self._violation), embedder
        self.state_dir = Path(state_dir).resolve()
        if self.state_dir == (Path.home() / ".mem0").resolve():
            raise ValueError("Mem0 comparison state must not use HOME/.mem0")
        if not isinstance(run_id, str) or not run_id.strip():
            raise ValueError("run_id must be a nonempty string")
        self.run_id = run_id
        self.fingerprint = getattr(embedder, "fingerprint", None)
        if not isinstance(self.fingerprint, str) or not self.fingerprint.strip():
            raise ValueError("Mem0 comparison requires an explicit embedding fingerprint")
        try:
            self.sdk_version = importlib.metadata.version("mem0ai")
        except importlib.metadata.PackageNotFoundError:
            raise MemoryBackendError("Mem0 comparison requires the pinned optional mem0ai dependency") from None
        if self.sdk_version != SUPPORTED_MEM0_VERSION:
            raise MemoryBackendError(f"controlled Mem0 adapter requires mem0ai=={SUPPORTED_MEM0_VERSION}")
        self.sdk_versions = {"mem0ai": self.sdk_version,
                             "qdrant-client": importlib.metadata.version("qdrant-client"),
                             "openai": importlib.metadata.version("openai")}
        if any(importlib.util.find_spec(name) is not None for name in ("spacy", "fastembed")):
            raise MemoryBackendError("controlled Mem0 profile requires isolated runtime without spacy/fastembed; automatic model downloads are disabled")
        self._lock = threading.RLock()
        self._memory = self._bridge = self._qdrant = None
        self._closed = False
        self.scope_violation_count = 0
        self.index_seconds = self.search_seconds = 0.0
        self.sdk_state_directory = None
        self._manifest_path = self.state_dir / "snapshots.json"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        if self._manifest_path.exists():
            self._manifest = json.loads(self._manifest_path.read_text(encoding="utf-8"))
            expected = (1, self.run_id, self.fingerprint, self.sdk_version)
            actual = tuple(self._manifest.get(key) for key in ("schema_version", "run_id", "fingerprint", "sdk_version"))
            if actual != expected:
                raise MemoryBackendError("Mem0 run directory belongs to another run/model/schema; use an isolated directory")
            if any(item.get("status") != "ready" for item in self._manifest["snapshots"].values()):
                raise MemoryBackendError("Mem0 has an incomplete prior index; retain it for audit and use a fresh run directory")
        else:
            if (self.state_dir / "qdrant").exists() or (self.state_dir / "history.sqlite3").exists():
                raise MemoryBackendError("Mem0 state has no ownership manifest; use a fresh run directory")
            self._manifest = {"schema_version": 1, "run_id": self.run_id, "fingerprint": self.fingerprint,
                              "sdk_version": self.sdk_version, "dimension": self._configured_dimension(), "snapshots": {}}
            self._write_manifest()

    def _configured_dimension(self):
        values = [getattr(self.embedder, "dimension", None), getattr(self.embedder, "embedding_dimension", None),
                  getattr(getattr(self.embedder, "config", None), "embedding_dimensions", None)]
        return next((value for value in values if type(value) is int and 0 < value <= 65536), None)

    def _write_manifest(self):
        temporary = self._manifest_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(self._manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        temporary.replace(self._manifest_path)

    def _check_open(self):
        if self._closed:
            raise MemoryBackendError("Mem0 provider is closed")

    def _snapshot(self, project_id, known_at):
        events = self.store.project_events(project_id, known_at=known_at)
        if any(event.project_id != project_id or (known_at is not None and event.observed_at > known_at) for event in events):
            self._violation("readout adapter returned events outside project/known_at")
        documents = build_documents(events)
        summaries = []
        for document in documents:
            matching = [event for event in events if (event.subject, event.predicate) == (document["subject"], document["predicate"])]
            summaries.append({**document, "event_ids": sorted(event.event_id for event in matching),
                              "source_ids": sorted({event.source_id for event in matching})})
        cutoff = None if known_at is None else known_at.isoformat()
        scope_key = _digest([project_id, cutoff])
        identity = {"project_id": project_id, "known_at": cutoff, "fingerprint": self.fingerprint,
                    "documents": [{key: value for key, value in document.items() if key != "text"} for document in summaries]}
        return scope_key, "snapshot-" + _digest(identity), summaries

    def _ensure_memory(self, first_document=None):
        if self._memory is not None:
            return
        dimension = self._manifest["dimension"]
        prepared = None
        if dimension is None:
            if first_document is None:
                raise MemoryBackendError("cannot infer embedding dimensions without a property document")
            returned = self.embedder.embed([first_document["text"]])
            if not isinstance(returned, list) or len(returned) != 1:
                raise ValueError("embedding dimension probe returned the wrong vector count")
            prepared = validate_vector(returned[0], context="Mem0 embedding dimension probe")
            dimension = len(prepared)
            if dimension > 65536:
                raise ValueError("embedding dimension exceeds controlled limit")
            self._manifest["dimension"] = dimension
            self._write_manifest()
        config = getattr(self.embedder, "config", None)
        model = getattr(config, "embedding_model", None) or "repomind-shared-embedding"
        self._bridge = _EmbeddingBridge(self.embedder, model, dimension)
        if prepared is not None:
            self._bridge.prepared_documents[first_document["text"]] = prepared
        try:
            Memory, self.sdk_state_directory = _memory_class(self.state_dir / "sdk-state")
            from qdrant_client import QdrantClient
            self._qdrant = QdrantClient(path=str(self.state_dir / "qdrant"))
            with _IMPORT_LOCK, _safe_sdk_environment(self.state_dir / "sdk-state"):
                self._memory = Memory.from_config({
                    "vector_store": {"provider": "qdrant", "config": {
                        "client": self._qdrant, "path": str(self.state_dir / "qdrant"),
                        "collection_name": "repomind_controlled", "embedding_model_dims": dimension,
                    }},
                    "embedder": {"provider": "openai", "config": {
                        "model": model, "api_key": self._bridge.key,
                        "openai_base_url": self._bridge.url, "embedding_dims": dimension,
                    }},
                    "llm": {"provider": "openai", "config": {
                        "model": "repomind-inference-disabled", "api_key": self._bridge.key,
                        "openai_base_url": self._bridge.url, "enable_vision": False,
                        "temperature": 0, "max_tokens": 1,
                    }},
                    "history_db_path": str(self.state_dir / "history.sqlite3"), "version": "v1.1",
                })
        except Exception:
            self.close()
            raise

    def _violation(self, message):
        self.scope_violation_count += 1
        raise ScopeViolationError("Mem0 scope violation: " + message)

    def index(self, project_id: str, known_at: object | None = None) -> dict[str, Any]:
        project_id, known_at = scope(project_id, known_at)
        started = time.perf_counter()
        with self._lock:
            try:
                self._check_open()
                key, snapshot_id, documents = self._snapshot(project_id, known_at)
                previous = self._manifest["snapshots"].get(key)
                if previous and previous["status"] == "ready" and previous["snapshot_id"] == snapshot_id:
                    if documents:
                        self._ensure_memory(documents[0])
                    return {"provider": self.name, "project_id": project_id, "count": len(documents),
                            "requested": 0, "cached": len(documents), "snapshot_id": snapshot_id}
                if previous and previous["status"] != "ready":
                    raise MemoryBackendError("incomplete Mem0 index; retain audit state and use a fresh run directory")
                if documents:
                    self._ensure_memory(documents[0])
                record = {"project_id": project_id, "known_at": None if known_at is None else known_at.isoformat(),
                          "snapshot_id": snapshot_id, "status": "building", "documents": []}
                self._manifest["snapshots"][key] = record
                self._write_manifest()
                for document in documents:
                    metadata = {"project_id": project_id, "subject": document["subject"],
                                "predicate": document["predicate"], "text_hash": document["text_hash"],
                                "snapshot_id": snapshot_id, "source_ids": document["source_ids"],
                                "event_ids": document["event_ids"]}
                    self._bridge.operation = "document"
                    try:
                        response = self._memory.add(
                            [{"role": "user", "content": document["text"]}],
                            user_id="project-" + _digest(project_id), run_id=snapshot_id,
                            metadata=metadata, infer=False,
                        )
                    except Exception:
                        raise MemoryBackendError("Mem0 index failed; no backend fallback was applied; use a fresh run directory") from None
                    finally:
                        self._bridge.operation = None
                    rows = response.get("results") if isinstance(response, dict) else None
                    if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict)
                            or not isinstance(rows[0].get("id"), str) or rows[0].get("memory") != document["text"]
                            or rows[0].get("event") != "ADD"):
                        raise MemoryBackendError("Mem0 did not acknowledge the raw property document")
                    record["documents"].append(metadata | {"memory_id": rows[0]["id"]})
                record["status"] = "ready"
                self._write_manifest()
                return {"provider": self.name, "project_id": project_id, "count": len(documents),
                        "requested": len(documents), "cached": 0, "snapshot_id": snapshot_id}
            finally:
                self.index_seconds += time.perf_counter() - started

    def search(self, project_id: str, text: str, as_of: object, known_at: object | None = None,
               top_k: int = 3, min_cosine: float = 0.55) -> dict[str, Any]:
        project_id, text, as_of, known_at = request(project_id, text, as_of, known_at, top_k, min_cosine)
        started = time.perf_counter()
        with self._lock:
            try:
                self._check_open()
                key, snapshot_id, documents = self._snapshot(project_id, known_at)
                record = self._manifest["snapshots"].get(key)
                if not record or record["status"] != "ready" or record["snapshot_id"] != snapshot_id:
                    raise SearchIndexError("Mem0 index missing/stale for project/known_at; reindex this snapshot")
                output = {"provider": self.name, "project_id": project_id, "query": text,
                          "mode": "mem0_controlled_retrieval", "as_of": as_of.isoformat(),
                          "known_at": None if known_at is None else known_at.isoformat(),
                          "top_k": top_k, "min_cosine": float(min_cosine),
                          "indexed_documents": len(documents), "snapshot_id": snapshot_id, "hits": []}
                if not documents:
                    return output
                self._ensure_memory(documents[0])
                user_id = "project-" + _digest(project_id)
                self._bridge.operation = "query"
                try:
                    response = self._memory.search(text, top_k=top_k,
                        filters={"user_id": user_id, "run_id": snapshot_id,
                                 "project_id": project_id, "snapshot_id": snapshot_id},
                        threshold=min_cosine, rerank=False, explain=True)
                except Exception:
                    raise MemoryBackendError("Mem0 search failed; no native fallback or gold supplementation was applied") from None
                finally:
                    self._bridge.operation = None
                rows = response.get("results") if isinstance(response, dict) else None
                if not isinstance(rows, list):
                    raise MemoryBackendError("Mem0 search returned a malformed result list")
                if len(rows) > top_k:
                    raise MemoryBackendError("Mem0 returned more candidates than the shared top_k")
                by_id = {document["memory_id"]: document for document in record["documents"]}
                texts = {(document["subject"], document["predicate"]): document["text"] for document in documents}
                seen = set()
                for rank, row in enumerate(rows, 1):
                    if not isinstance(row, dict):
                        self._violation("result has no auditable metadata")
                    metadata = row.get("metadata")
                    expected = by_id.get(row.get("id"))
                    if (expected is None or not isinstance(metadata, dict)
                            or row.get("user_id") != user_id or row.get("run_id") != snapshot_id
                            or any(metadata.get(field) != expected[field] for field in
                                   ("project_id", "subject", "predicate", "text_hash", "snapshot_id", "source_ids", "event_ids"))):
                        self._violation("returned project, snapshot or fact/source mapping differs")
                    fact_key = expected["subject"], expected["predicate"]
                    if fact_key in seen or row.get("memory") != texts[fact_key]:
                        self._violation("duplicate or changed property document")
                    seen.add(fact_key)
                    details = row.get("score_details")
                    semantic = details.get("semantic_score") if isinstance(details, dict) else None
                    score = row.get("score")
                    if any(isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value)
                           for value in (semantic, score)) or not -1.00001 <= semantic <= 1.00001:
                        raise MemoryBackendError("Mem0 explanation lacks a finite raw semantic score")
                    if semantic <= min_cosine:
                        continue
                    result = MemoryRetriever(self.store).query(MemoryQuery(
                        project_id=project_id, subject=fact_key[0], predicate=fact_key[1],
                        as_of=as_of, known_at=known_at,
                    ))
                    output["hits"].append({"subject": fact_key[0], "predicate": fact_key[1],
                        "score": float(score), "semantic_score": float(semantic),
                        "lexical_score": details.get("bm25_score", 0.0), "backend_rank": rank,
                        "backend_memory_id": row["id"], "result": result.model_dump(mode="json")})
                return output
            finally:
                self.search_seconds += time.perf_counter() - started

    def safe_metadata(self) -> dict[str, Any]:
        return {"name": self.name, "sdk_version": self.sdk_version,
                "sdk_versions": dict(self.sdk_versions),
                "comparison_scope": "controlled retrieval backend only; infer=False; shared V1 resolver",
                "state_dir": str(self.state_dir), "sdk_state_directory": self.sdk_state_directory,
                "run_id": self.run_id, "embedding": embedding_metadata(self.embedder),
                "scope_violation_count": self.scope_violation_count,
                "optional_nlp": False, "optional_bm25_encoder": False,
                "backend_ranking": "Mem0 semantic + available BM25/entity; pinned profile has optional features absent",
                "threshold_policy": "SDK raw semantic threshold, then strict > min_cosine; preserve SDK rank; no top-up",
                "query_normalization": "strip and replace LF with space",
                "telemetry": False, "dimension": self._manifest["dimension"],
                "index_seconds_including_bridge": self.index_seconds,
                "search_seconds_including_bridge": self.search_seconds,
                "bridge": None if self._bridge is None else self._bridge.metadata()}

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            errors = []
            if self._memory is not None:
                # Public SDK close releases history, but not its Qdrant client.
                for component in (self._memory.embedding_model, self._memory.llm):
                    client = getattr(component, "client", None)
                    if callable(getattr(client, "close", None)):
                        try:
                            client.close()
                        except Exception:
                            errors.append("SDK HTTP client")
                try:
                    self._memory.close()
                except Exception:
                    errors.append("history")
            if self._qdrant is not None:
                try:
                    self._qdrant.close()
                except Exception:
                    errors.append("Qdrant")
            if self._bridge is not None:
                self._bridge.close()
            if errors:
                raise MemoryBackendError("Mem0 resource close failed: " + ", ".join(errors))

    def __enter__(self):
        self._check_open()
        return self

    def __exit__(self, *args):
        self.close()
