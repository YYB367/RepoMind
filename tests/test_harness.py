import json
from pathlib import Path

import pytest

from repomind.agent.workspace import digest
from repomind.harness.experiment import choose_challenger, promotion_reason, run_phase
from repomind.harness.policy import finish_feedback, history_receipt

ROOT = Path(__file__).resolve().parents[1]


def test_historical_nomination_is_hash_checked_and_returns_only_counts():
    path = ROOT / "reports/v2/live-dev-r2.traces.jsonl"
    receipt = history_receipt(path, digest(path))
    assert receipt["traces"] == 18
    assert receipt["verified_but_unfinished"] > 0 and receipt["successful_write_events"] > 0
    assert receipt["candidates"] == ["reference", "compact", "guided", "compact-guided"]
    assert set(receipt) == {"sha256", "traces", "run_id", "verified_but_unfinished",
                            "successful_write_events", "candidates", "kind"}
    with pytest.raises(ValueError, match="differs from frozen"):
        history_receipt(path, "0" * 64)


def test_guidance_rejects_public_results_made_stale_by_writes():
    write = {"tool": "write_file", "status": "ok"}
    passed = {"tool": "run_tests", "status": "ok", "result": {"passed": True}}
    diff = {"tool": "git_diff", "status": "ok", "result": {"diff": "changed"}}
    assert "send finish" in finish_feedback([write, passed, diff], 1)
    assert finish_feedback([write, passed, diff, write], 1) is None
    assert finish_feedback([write, passed, diff], 0) is None


def _metrics(**updates):
    return {"strict": 3, "code_verified": 4, "input_tokens": 900, "output_tokens": 100,
            "infrastructure_errors": 0, "resolved_models": ["model"], **updates}


def test_rank_and_promotion_prefer_quality_and_require_live_cost_evidence():
    reference = _metrics()
    compact = reference | {"input_tokens": 800}
    guided = reference | {"strict": 4, "input_tokens": 1100}
    assert choose_challenger({"reference": reference, "compact": compact, "guided": guided}) == "guided"
    assert promotion_reason(reference, compact, live=True) == "token_saving_at_equal_or_better_quality"
    assert promotion_reason(reference, guided, live=True) == "strict_completion_gain"
    assert promotion_reason(reference, compact | {"input_tokens": 801}, live=True) == "no_threshold_gain"
    assert promotion_reason(reference, compact | {"code_verified": 3}, live=True) == "quality_regression"
    assert promotion_reason(reference, compact | {"resolved_models": ["different"]}, live=True) == "model_identity_unverified"
    assert promotion_reason(reference, compact, live=False) == "scripted_replay"


def test_validate_needs_lock_before_opening_holdout_or_docker(tmp_path):
    suite = tmp_path / "suite"
    suite.mkdir()
    (suite / "protocol.json").write_text(json.dumps({"version": 1, "repetitions": 2}), encoding="utf-8")
    run = tmp_path / "run"
    run.mkdir()
    (run / "selection-lock.json").write_text("{}", encoding="utf-8")
    (run / "dev.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="selection lock"):
        run_phase("validate", suite=suite, history=None, run_dir=run,
                  image="unavailable", config_dir=tmp_path)
    assert not (run / "holdout").exists()
    with pytest.raises(ValueError, match="fresh run directory"):
        run_phase("tune", suite=suite, history=None, run_dir=run,
                  image="unavailable", config_dir=tmp_path)
