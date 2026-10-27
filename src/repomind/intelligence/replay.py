"""Recorded embedding vectors for contract replay, never a semantic-quality benchmark."""

import hashlib
import json
import math
from pathlib import Path

from repomind.memory.store import _unique_keys


class RecordedEmbedder:
    name = "recorded-embedding-test-double-not-live"

    def __init__(self, path: str | Path):
        data = json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_keys)
        if data.get("kind") != "recorded_test_double":
            raise ValueError("recorded vectors must declare kind=recorded_test_double")
        self.fingerprint = data["fingerprint"]
        if not isinstance(self.fingerprint, str) or not self.fingerprint.startswith("recorded:"):
            raise ValueError("recorded vector fingerprint must start with recorded:")
        self._vectors = {}
        dimensions = set()
        for record in data["records"]:
            key, vector = record["text_sha256"], record["vector"]
            if key in self._vectors:
                raise ValueError("duplicate text hash in recorded vectors")
            if (not isinstance(key, str) or len(key) != 64 or not isinstance(vector, list) or not vector
                or any(isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) for v in vector)
                or not 0 < math.hypot(*vector) < math.inf):
                raise ValueError("invalid recorded vector")
            dimensions.add(len(vector))
            self._vectors[key] = [float(v) for v in vector]
        if len(dimensions) > 1:
            raise ValueError("recorded vectors must have one dimension")

    def embed(self, texts: list[str]) -> list[list[float]]:
        output = []
        for text in texts:
            key = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if key not in self._vectors:
                raise ValueError("no recorded vector for this exact text; replay is not a real embedding model")
            output.append(self._vectors[key].copy())
        return output
