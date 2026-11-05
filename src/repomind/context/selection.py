"""Scope, rank, and pack complete evidence records under a shared budget."""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field

from repomind.intelligence.providers import _json_loads
from repomind.intelligence.search import cosine_similarity, validate_vector

STRATEGIES = ("direct", "vector", "layered")
Identifier = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9-]{0,47}$")]
Text = Annotated[str, Field(min_length=1, max_length=16000)]
Reader = Callable[[str, str, str, str | None], str]


class ContextModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class Document(ContextModel):
    id: Identifier
    title: Text
    body: Text


class Group(ContextModel):
    id: Identifier
    abstract: Text
    overview: Text
    documents: tuple[Document, ...] = Field(min_length=1, max_length=50)


class Corpus(ContextModel):
    projects: dict[Identifier, tuple[Group, ...]] = Field(min_length=1, max_length=32)

    @classmethod
    def load(cls, path: Path) -> Corpus:
        corpus = cls.model_validate(_json_loads(path.read_bytes()))
        for groups in corpus.projects.values():
            if not 1 <= len(groups) <= 32 or len({group.id for group in groups}) != len(groups):
                raise ValueError("project must contain 1 to 32 uniquely named context groups")
            ids = [doc.id for group in groups for doc in group.documents]
            if len(set(ids)) != len(ids):
                raise ValueError("document IDs must be unique within each project")
        return corpus

    def groups(self, project: str) -> tuple[Group, ...]:
        if project not in self.projects:
            raise ValueError("unknown context project")
        return self.projects[project]


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


def evidence_json(records: list[dict] | dict) -> str:
    return json.dumps(records, ensure_ascii=False, separators=(",", ":"))


def _bytes(text: str) -> int:
    return len(text.encode("utf-8"))


def _words(text: str) -> set[str]:
    words = set(re.findall(r"[a-z0-9]+", text.casefold()))
    for span in re.findall(r"[\u3400-\u9fff]+", text):
        words.update(span[index:index + 2] for index in range(max(1, len(span) - 1)))
    return words


class ContextSelector:
    def __init__(self, corpus: Corpus, *, embedder: Embedder | None = None, reader: Reader | None = None):
        self.corpus = corpus
        self.embedder = embedder
        self.reader = reader
        self.indexes: dict[str, list[list[float]]] = {}

    def index(self, project: str) -> None:
        if self.embedder is None or self.reader is not None:
            raise ValueError("vector indexing requires a local corpus and configured embedder")
        documents = [doc for group in self.corpus.groups(project) for doc in group.documents]
        vectors = self.embedder.embed([doc.title + "\n" + doc.body for doc in documents])
        if len(vectors) != len(documents):
            raise ValueError("embedding count does not match project documents")
        validated = [validate_vector(vector) for vector in vectors]
        if len({len(vector) for vector in validated}) != 1:
            raise ValueError("embedding index contains inconsistent dimensions")
        self.indexes[project] = validated

    def select(self, project: str, query: str, strategy: str, budget: int) -> dict:
        if strategy not in STRATEGIES or type(budget) is not int or not 2 <= budget <= 32000:
            raise ValueError("unknown context strategy or invalid evidence byte budget (2–32000)")
        if not 1 <= len(query.strip()) <= 2000:
            raise ValueError("context query must contain 1 to 2000 characters")
        if self.reader is not None and strategy != "layered":
            raise ValueError("OpenViking reading is available for layered selection")
        groups = self.corpus.groups(project)
        started = perf_counter()
        visits: list[dict] = []

        def read(level: str, group: Group, doc: Document | None = None) -> str:
            doc_id = doc.id if doc else None
            if self.reader is not None:
                value = self.reader(level, project, group.id, doc_id)
            elif doc is not None:
                value = doc.body
            else:
                value = group.abstract if level == "L0" else group.overview
            visits.append({"level": level, "group": group.id, "source_id": doc_id, "bytes": _bytes(value)})
            return value

        candidates = [(group, doc) for group in groups for doc in group.documents]
        query_terms = _words(query)
        if strategy == "vector":
            if self.embedder is None or project not in self.indexes:
                raise ValueError("build the project vector index before selection")
            embed_query = getattr(self.embedder, "embed_query", None)
            vector = validate_vector(embed_query(query) if embed_query else self.embedder.embed([query])[0])
            scores = [cosine_similarity(vector, item) for item in self.indexes[project]]
            candidates = [candidates[i] for i in sorted(range(len(scores)), key=lambda i: (-scores[i], i))]
        elif strategy == "layered":
            ranked_groups = [(len(query_terms & _words(read("L0", group))), group) for group in groups]
            ranked_groups.sort(key=lambda item: -item[0])
            relevant = [group for score, group in ranked_groups if score > 0][:2]
            overviews = {group.id: read("L1", group) for group in relevant or [ranked_groups[0][1]]}
            ranked_documents = []
            for group in relevant or [ranked_groups[0][1]]:
                for doc in group.documents:
                    detail = " ".join(line for line in overviews[group.id].splitlines()
                                      if doc.id in line or doc.title.casefold() in line.casefold())
                    score = len(query_terms & _words(doc.title + " " + detail))
                    ranked_documents.append((score, group, doc))
            ranked_documents.sort(key=lambda item: -item[0])
            candidates = [(group, doc) for _, group, doc in ranked_documents]

        records: list[dict] = []
        size = _bytes(evidence_json(records))
        for group, doc in candidates:
            if size >= budget:
                break
            # Local lengths are known from the snapshot. Remote bodies are measured after retrieval.
            item = {"source_id": doc.id, "text": doc.body}
            if self.reader is None and _bytes(evidence_json([*records, item])) > budget:
                continue
            item["text"] = read("L2", group, doc)
            next_size = _bytes(evidence_json([*records, item]))
            if next_size <= budget:
                records.append(item)
                size = next_size
        return {
            "project": project, "strategy": strategy, "backend": "openviking" if self.reader else "local",
            "budget_bytes": budget, "evidence_bytes": size, "evidence": records,
            "retrieval_ms": (perf_counter() - started) * 1000, "visits": visits,
            "retrieved_bytes": sum(visit["bytes"] for visit in visits),
        }
