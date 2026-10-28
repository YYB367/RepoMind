"""Measure actual embedding calls and compare input/vector digests without keys."""

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from time import perf_counter

from repomind.intelligence.search import validate_vector


def _digest(value) -> str:
    if isinstance(value, str):
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class MeasuredEmbedder:
    def __init__(self, provider, *, live: bool):
        self.provider, self.live, self.calls = provider, live, []
        self._initial_usage = self._provider_counts("usage") or {}
        self._initial_reports = self._provider_counts("usage_report_counts")
        value = getattr(provider, "request_count", 0 if not live else None)
        self._initial_requests = value if type(value) is int and value >= 0 else None

    def _provider_counts(self, name):
        try:
            values = getattr(self.provider, name, None)
        except Exception:
            return None
        if not isinstance(values, dict) or any(not isinstance(key, str) or type(value) is not int or value < 0 for key, value in values.items()):
            return None
        return dict(values)

    @staticmethod
    def _relative(after, before):
        if after is None or before is None:
            return None
        if any(after.get(key, 0) < value for key, value in before.items()):
            return None
        return {key: value - before.get(key, 0) for key, value in after.items()}

    @property
    def name(self):
        return getattr(self.provider, "name", "embedding-provider")

    @property
    def fingerprint(self):
        return self.provider.fingerprint

    @property
    def config(self):
        return getattr(self.provider, "config", None)

    @property
    def dimension(self):
        explicit = getattr(self.provider, "dimension", None)
        config = self.config
        return explicit or getattr(config, "embedding_dimensions", None) or self.embedding_dimension

    @property
    def embedding_dimension(self):
        return getattr(self.provider, "embedding_dimension", None)

    @property
    def usage(self):
        return self._relative(self._provider_counts("usage"), self._initial_usage) or {}

    @property
    def usage_report_counts(self):
        return self._relative(self._provider_counts("usage_report_counts"), self._initial_reports)

    @staticmethod
    def _complete(requests, reports):
        return (type(requests) is int and requests > 0 and isinstance(reports, dict)
                and any(reports.get(name) == requests for name in ("prompt_tokens", "input_tokens"))
                and all(value == requests for value in reports.values()))

    @property
    def usage_complete(self):
        return (self._complete(self.request_count, self.usage_report_counts)
                and self._provider_counts("usage") is not None
                and not any(call.get("counter_reset") for call in self.calls))

    @property
    def request_count(self):
        try:
            current = getattr(self.provider, "request_count", 0 if not self.live else None)
        except Exception:
            return None
        if type(current) is not int or self._initial_requests is None or current < self._initial_requests:
            return None
        return current - self._initial_requests

    def _invoke(self, texts, kind):
        before = self.usage
        count_before = self.request_count
        reports_before = self.usage_report_counts
        started_at = datetime.now(timezone.utc).isoformat()
        started, error, vectors = perf_counter(), None, None
        try:
            query_method = getattr(self.provider, "embed_query", None)
            vectors = ([query_method(texts[0])] if kind == "query" and callable(query_method)
                       else self.provider.embed(texts))
            if not isinstance(vectors, list) or len(vectors) != len(texts):
                raise ValueError("embedding provider returned wrong vector count")
            vectors = [validate_vector(vector) for vector in vectors]
            return vectors
        except Exception as exc:
            error = type(exc).__name__
            vectors = None
            raise
        finally:
            after, count_after = self.usage, self.request_count
            delta = self._relative(after, before)
            requests = (count_after-count_before if type(count_after) is int and type(count_before) is int
                        and count_after >= count_before else None)
            report_delta = self._relative(self.usage_report_counts, reports_before)
            counter_reset = (delta is None or self._provider_counts("usage") is None
                             or (count_before is not None and (count_after is None or requests is None)))
            if delta is not None:
                delta = {key: value for key, value in delta.items()
                         if (report_delta.get(key, 0) > 0 if isinstance(report_delta, dict) else value > 0)}
            self.calls.append({"operation": kind, "input_hashes": [_digest(text) for text in texts],
                "vector_hashes": None if vectors is None else [_digest(vector) for vector in vectors],
                "elapsed_seconds": perf_counter() - started, "usage_delta": delta or {},
                "started_at": started_at, "ended_at": datetime.now(timezone.utc).isoformat(),
                "usage_report_counts": report_delta, "usage_complete": self._complete(requests, report_delta) and not counter_reset,
                "remote_request_delta": requests, "counter_reset": counter_reset, "error_type": error})

    def embed(self, texts):
        return self._invoke(texts, "document")

    def embed_query(self, text):
        return self._invoke([text], "query")[0]

    def safe_metadata(self):
        method = getattr(self.provider, "safe_metadata", None)
        info = method() if callable(method) else {"name": self.name, "fingerprint": self.fingerprint}
        return {**info, "live": self.live, "request_count": self.request_count, "usage": self.usage,
                "usage_report_counts": self.usage_report_counts, "usage_complete": self.usage_complete,
                "measured_calls": deepcopy(self.calls)}
