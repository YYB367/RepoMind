import hashlib
import json

import pytest

from repomind.intelligence.ingestion import validate_output_paths
from repomind.intelligence.replay import RecordedEmbedder


def file(tmp_path, records, **changes):
    payload = {"kind": "recorded_test_double", "fingerprint": "recorded:test", "records": records}
    payload.update(changes)
    path = tmp_path / "vectors.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_recorded_vectors_require_exact_inputs_and_do_not_guess(tmp_path):
    key = hashlib.sha256("database".encode()).hexdigest()
    provider = RecordedEmbedder(file(tmp_path, [{"text_sha256": key, "vector": [1, 0]}]))
    assert provider.embed(["database"]) == [[1.0, 0.0]]
    with pytest.raises(ValueError, match="not a real embedding"):
        provider.embed(["unrecorded paraphrase"])


@pytest.mark.parametrize("records,changes", [
    ([{"text_sha256": "a"*64, "vector": [0, 0]}], {}),
    ([{"text_sha256": "a"*64, "vector": [float("nan"), 1]}], {}),
    ([{"text_sha256": "a"*64, "vector": [1]}, {"text_sha256": "b"*64, "vector": [1, 0]}], {}),
    ([{"text_sha256": "a"*64, "vector": [1]}, {"text_sha256": "a"*64, "vector": [1]}], {}),
    ([], {"kind": "a real model"}), ([], {"fingerprint": "pretend-live"}),
])
def test_recorded_vectors_reject_misleading_or_invalid_inputs(tmp_path, records, changes):
    with pytest.raises(ValueError):
        RecordedEmbedder(file(tmp_path, records, **changes))


def test_candidate_output_cannot_replace_api_key_configuration(tmp_path):
    path = tmp_path / ".env"
    path.write_text("DEEPSEEK_API_KEY=synthetic-only", encoding="utf-8")
    with pytest.raises(ValueError, match="configuration"):
        validate_output_paths(path, [])
    assert path.read_text(encoding="utf-8") == "DEEPSEEK_API_KEY=synthetic-only"
