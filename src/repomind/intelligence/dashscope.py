"""Native DashScope text embeddings; chat credentials are never used here."""

import hashlib
import json
import os

from repomind.intelligence.config import load_env_file
from repomind.intelligence.providers import OpenAICompatibleProvider, ProviderConfig
from repomind.intelligence.search import validate_vector


class DashScopeEmbeddingProvider:
    def __init__(self, config: ProviderConfig):
        if config.embedding_model is None:
            raise ValueError("DashScope embedding model is not configured")
        if config.api_key is None:
            raise ValueError("DashScope embedding API key is not configured")
        self.config = config
        self._client = OpenAICompatibleProvider(config)
        self.dimension = config.embedding_dimensions or 1024
        self.embedding_dimension = None
        self._input_tokens = None

    @property
    def name(self) -> str:
        return "dashscope-native:" + self.config.embedding_model

    @property
    def fingerprint(self) -> str:
        identity = {"adapter": "dashscope-native-v1", "base_url": self.config.base_url,
                    "model": self.config.embedding_model, "dimension": self.dimension,
                    "output_type": "dense", "text_type": "documents=document;queries=query"}
        return "dashscope-" + hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()

    @property
    def request_count(self) -> int:
        return self._client.request_count

    @property
    def usage(self) -> dict:
        result = self._client.usage.copy()
        if self._input_tokens is not None:
            result["input_tokens"] = self._input_tokens
        return result

    def safe_metadata(self) -> dict:
        return {"name": self.name, "base_url": self.config.base_url, "model": self.config.embedding_model,
                "dimension": self.dimension, "fingerprint": self.fingerprint,
                "text_type_policy": "documents=document;queries=query", "batch_limit": 20,
                "request_count": self.request_count, "usage": self.usage}

    def _embed(self, texts: list[str], text_type: str) -> list[list[float]]:
        if not isinstance(texts, list) or any(not isinstance(text, str) or not text.strip() for text in texts):
            raise ValueError("DashScope inputs must be nonempty strings")
        vectors = []
        for offset in range(0, len(texts), 20):
            chunk = texts[offset:offset + 20]
            payload = {"model": self.config.embedding_model, "input": {"texts": chunk},
                       "parameters": {"text_type": text_type, "dimension": self.dimension, "output_type": "dense"}}
            response = self._client._post("/services/embeddings/text-embedding/text-embedding", payload)
            if response.get("code") or response.get("status_code", 200) != 200:
                raise ValueError("DashScope returned an API error; check endpoint, model and credentials")
            output = response.get("output")
            records = output.get("embeddings") if isinstance(output, dict) else None
            if not isinstance(records, list) or len(records) != len(chunk):
                raise ValueError("DashScope returned the wrong embedding count or malformed output")
            by_index = {}
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError("DashScope returned a malformed embedding record")
                index = record.get("text_index")
                if type(index) is not int or not 0 <= index < len(chunk) or index in by_index:
                    raise ValueError("DashScope text_index values must be unique and complete")
                vector = validate_vector(record.get("embedding"), context="DashScope embedding")
                if len(vector) != self.dimension:
                    raise ValueError("DashScope embedding dimension differs from configured dimension")
                by_index[index] = vector
            usage = response.get("usage")
            if isinstance(usage, dict) and type(usage.get("input_tokens")) is int and usage["input_tokens"] >= 0:
                self._input_tokens = (self._input_tokens or 0) + usage["input_tokens"]
            vectors.extend(by_index[index] for index in range(len(chunk)))
            self.embedding_dimension = self.dimension
        return vectors

    def embed(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "document")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "query")[0]


def embedding_provider_from_env():
    load_env_file()
    config = ProviderConfig.embedding_from_env()
    kind = os.getenv("REPOMIND_EMBEDDING_PROVIDER", "openai-compatible").strip().lower()
    dimensions = os.getenv("REPOMIND_EMBEDDING_DIMENSIONS")
    if dimensions:
        config = ProviderConfig.model_validate({**config.model_dump(), "api_key": config.api_key,
                                               "embedding_dimensions": dimensions})
    if kind == "dashscope":
        return DashScopeEmbeddingProvider(config)
    if kind in ("openai", "openai-compatible"):
        if config.api_key is None:
            raise ValueError("embedding API key is not configured")
        return OpenAICompatibleProvider(config)
    raise ValueError("REPOMIND_EMBEDDING_PROVIDER must be dashscope or openai-compatible")
