"""Dataset identity checks read holdout bytes only, never use answers for tuning."""

import hashlib
import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("folder", ["data", "data/v1.1"])
def test_frozen_dataset_hashes_survive_distribution(folder):
    root = Path(__file__).resolve().parents[1] / folder
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for relative, record in manifest["files"].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == record["sha256"], relative
