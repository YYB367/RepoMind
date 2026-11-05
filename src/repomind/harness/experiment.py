"""Select a harness on development tasks and test the locked challenger independently."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path

from repomind import __version__
from repomind.agent.benchmark import load_tasks
from repomind.agent.loop import run_agent
from repomind.agent.models import AgentBudget
from repomind.agent.providers import LiveAgentProvider, ReplayAgentProvider, PROMPT_SHA256
from repomind.agent.sandbox import DockerSandbox
from repomind.agent.workspace import TaskWorkspace, checked_path, digest
from repomind.evaluation.intelligent import _implementation_hash
from repomind.harness.policy import POLICIES, RECOVERY_POLICIES, REFERENCE, finish_feedback, history_receipt, recovery_receipt
from repomind.intelligence.providers import ProviderConfig, _json_loads
from repomind.platform.tracing import clean_payload

GOAL = "V3.0: select a finite harness on development tasks and independently test promotion"
RECOVERY_GOAL = "V3.0 recovery: preserve budget guidance after protocol errors and independently test it"
BUDGET = AgentBudget()
REPETITIONS = 2


def _read(path):
    value = _json_loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("expected a JSON object")
    return value


def _write(path, value):
    # Exclusive creation preserves partial-run evidence and previous receipts.
    body = json.dumps(clean_payload(value), ensure_ascii=False, allow_nan=False, indent=2)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(body + "\n")


def _inputs(root, split, protocol):
    folder = root / split
    manifest_path = checked_path(folder, "manifest.json")
    if digest(manifest_path) != protocol["manifests"][split]:
        raise ValueError("split manifest differs from frozen V3 protocol")
    manifest = _read(manifest_path)
    if manifest.get("split") != split or manifest.get("version") != 1:
        raise ValueError("invalid V3 split manifest")
    files = manifest["files"]
    if not {"tasks.jsonl", "recorded-actions.jsonl"} <= files.keys():
        raise ValueError("V3 split is incomplete")
    for name, sha in files.items():
        if digest(checked_path(folder, name)) != sha:
            raise ValueError(f"V3 split input differs from manifest: {name}")
    tasks = load_tasks(folder / "tasks.jsonl")
    expected = 3 if split == "dev" else 4
    prefix = "dev-" if split == "dev" else "hold-"
    if len(tasks) != expected or any(not task.task_id.startswith(prefix) for task in tasks):
        raise ValueError("V3 tasks do not match their frozen split")
    for task in tasks:
        if (task.public_test != f"public/{task.task_id}/test_public.py"
                or task.acceptance_test != f"judges/{task.task_id}/test_acceptance.py"
                or not {task.public_test, task.acceptance_test} <= files.keys()):
            raise ValueError("tests must be registered in the assigned split")
    return folder, tasks


def _trial(folder, task, path, name, sandbox, config):
    recovery = name in RECOVERY_POLICIES
    compact, guided = (RECOVERY_POLICIES if recovery else POLICIES)[name]
    workspace = TaskWorkspace(path / "repo", task, folder)
    provider = (LiveAgentProvider(config) if config is not None else
                ReplayAgentProvider(folder / "recorded-actions.jsonl", task.task_id))
    context = {"mode": "baseline", "facts": [], "experiences": []}
    agent = run_agent(task, workspace, provider, sandbox, context, budget=BUDGET,
                      compact_writes=compact, feedback=finish_feedback if guided else None,
                      feedback_on_protocol_error=recovery)
    public = hidden = None
    infrastructure = (
        agent["status"] in {"model_transport_error", "sandbox_error"}
        or any(step["status"] == "error" and step["tool"] != "model" for step in agent["observations"])
    )
    if not infrastructure:
        public = sandbox.run_tests(workspace.root, expected_count=task.public_count)
        infrastructure = public["infrastructure_error"]
        if not infrastructure:
            judge = path / "judge"
            judge.mkdir()
            (judge / "test_acceptance.py").write_bytes(checked_path(folder, task.acceptance_test).read_bytes())
            hidden = sandbox.run_tests(workspace.root, expected_count=task.acceptance_count, judge_dir=judge)
            infrastructure = hidden["infrastructure_error"]
    workspace.protected_integrity()
    verified = bool(not infrastructure and public and public["passed"] and hidden and hidden["passed"])
    return {
        "task_id": task.task_id, "policy": name, "agent": agent, "model_calls": provider.calls,
        "public_grading": public, "hidden_grading": hidden, "code_verified": verified,
        "strict_success": bool(verified and agent["changed_files"] and agent["status"] == "finished"),
        "infrastructure_error": infrastructure, "hidden_feedback_to_model": False,
    }


def _run(directory, folder, tasks, names, repeats, sandbox, config):
    trials = []
    for repeat in range(repeats):
        for index, task in enumerate(tasks):
            offset = (index + repeat) % len(names)
            for name in names[offset:] + names[:offset]:
                path = directory / f"repeat-{repeat + 1}" / task.task_id / name
                path.mkdir(parents=True, exist_ok=False)
                result = _trial(folder, task, path, name, sandbox, config)
                result["repeat"] = repeat + 1
                _write(path / "result.json", result)
                trials.append(result)
    return trials


def _summarize(trials, names):
    metrics = {}
    for name in names:
        rows = [row for row in trials if row["policy"] == name]
        calls = [call for row in rows for call in row["model_calls"]]
        usage = Counter()
        for call in calls:
            usage.update(call["usage"])
        complete = bool(calls) and all(call["usage_complete"] for call in calls)
        metrics[name] = {
            "tasks": len(rows), "strict": sum(row["strict_success"] for row in rows),
            "code_verified": sum(row["code_verified"] for row in rows),
            "infrastructure_errors": sum(row["infrastructure_error"] for row in rows),
            "requests": len(calls), "input_tokens": usage.get("prompt_tokens", usage.get("input_tokens")) if complete else None,
            "output_tokens": usage.get("completion_tokens", usage.get("output_tokens")) if complete else None,
            "resolved_models": sorted({str(call["resolved_model"]) for call in calls}),
            "stop_counts": dict(Counter(row["agent"]["status"] for row in rows)),
        }
    return metrics


def _token_total(metrics):
    if metrics["input_tokens"] is None or metrics["output_tokens"] is None:
        return None
    return metrics["input_tokens"] + metrics["output_tokens"]


def choose_challenger(metrics):
    def rank(name):
        row = metrics[name]
        tokens = _token_total(row)
        return (-row["strict"], -row["code_verified"], tokens if tokens is not None else float("inf"), name)

    eligible = [name for name in (*POLICIES, *RECOVERY_POLICIES) if name != REFERENCE and name in metrics]
    if not eligible or any(row["infrastructure_errors"] for row in metrics.values()):
        raise ValueError("development evidence has no usable comparison; no challenger locked")
    return min(eligible, key=rank)


def promotion_reason(reference, challenger, *, live):
    if not live:
        return "scripted_replay"
    if reference["infrastructure_errors"] or challenger["infrastructure_errors"]:
        return "infrastructure_error"
    if (len(reference["resolved_models"]) != 1 or reference["resolved_models"] != challenger["resolved_models"]
            or reference["resolved_models"] == ["None"]):
        return "model_identity_unverified"
    if challenger["strict"] < reference["strict"] or challenger["code_verified"] < reference["code_verified"]:
        return "quality_regression"
    if challenger["strict"] > reference["strict"]:
        return "strict_completion_gain"
    a, b = _token_total(reference), _token_total(challenger)
    if a and b is not None and 10 * b <= 9 * a:
        return "token_saving_at_equal_or_better_quality"
    return "no_threshold_gain"


def run_phase(phase, *, suite, history, run_dir, image, config_dir, live=False):
    if phase not in {"tune", "validate"}:
        raise ValueError("unknown harness phase")
    root, directory = Path(suite).resolve(), Path(run_dir).resolve()
    if directory.is_relative_to(root) or root.is_relative_to(directory):
        raise ValueError("use a dedicated run directory outside the frozen suite")
    protocol_path = checked_path(root, "protocol.json")
    protocol = _read(protocol_path)
    protocol_version = protocol.get("version")
    if protocol_version not in {1, 2} or protocol.get("repetitions") != REPETITIONS:
        raise ValueError("unsupported V3 protocol")
    goal = RECOVERY_GOAL if protocol_version == 2 else GOAL
    lock_path, dev_path = directory / "selection-lock.json", directory / "dev.json"
    split = "dev" if phase == "tune" else "holdout"
    if phase == "tune" and directory.exists():
        raise ValueError("tuning requires a fresh run directory")
    if phase == "validate" and ((directory / "holdout").exists() or (directory / "holdout.json").exists()):
        raise ValueError("holdout already started; use a new tune run for another experiment")

    # Read the lock and validate its provenance before touching holdout inputs.
    config = ProviderConfig.from_env() if live else None
    identity = {
        "version": __version__, "implementation_sha256": _implementation_hash(),
        "protocol_sha256": digest(protocol_path), "prompt_sha256": PROMPT_SHA256,
        "budget": BUDGET.model_dump(), "image": image, "mode": "live" if live else "replay",
        "model_config": config.safe_metadata() if config else None,
    }
    if phase == "validate":
        lock, dev = _read(lock_path), _read(dev_path)
        if (lock.get("identity") != identity or lock.get("dev_sha256") != digest(dev_path)
                or dev.get("identity") != identity or lock.get("challenger") != choose_challenger(dev["metrics"])):
            raise ValueError("selection lock no longer matches the development run")
        names = [REFERENCE, lock["challenger"]]
        provenance = {"selection_lock_sha256": digest(lock_path)}
    else:
        diagnose = recovery_receipt if protocol_version == 2 else history_receipt
        historical = diagnose(Path(history), protocol["history_sha256"])
        names = historical["candidates"]
        if len(names) < 2:
            raise ValueError("historical traces did not nominate a challenger")
        provenance = {"history": historical}

    folder, tasks = _inputs(root, split, protocol)
    sandbox = DockerSandbox(image, config_dir)
    sandbox_info = sandbox.probe()
    if live and (config.api_key is None or not config.chat_model):
        raise ValueError("live harness runs require a configured chat model and key")
    if phase == "tune":
        directory.mkdir(parents=True, exist_ok=False)
    run = directory / split
    run.mkdir(exist_ok=False)
    repeats = REPETITIONS if phase == "validate" else 1
    trials = _run(run, folder, tasks, names, repeats, sandbox, config)
    metrics = _summarize(trials, names)
    report = {
        "stage_goal": goal, "identity": identity, "sandbox": sandbox_info, "split": split, "metrics": metrics,
        "max_model_requests": len(tasks) * len(names) * repeats * BUDGET.max_turns,
        "created_at": datetime.now(timezone.utc).isoformat(), **provenance,
        "trials": [{key: row[key] for key in ("task_id", "policy", "repeat", "strict_success", "code_verified",
                                              "infrastructure_error", "hidden_feedback_to_model")}
                   for row in trials],
        "completed_without_infrastructure_errors": all(not row["infrastructure_error"] for row in trials),
    }
    if phase == "tune":
        _write(dev_path, report)
        challenger = choose_challenger(metrics)
        lock = {"stage_goal": goal, "identity": identity, "challenger": challenger, "dev_sha256": digest(dev_path)}
        _write(lock_path, lock)
        report["locked_challenger"] = challenger
    else:
        challenger = names[1]
        report["repetitions"] = [
            _summarize([row for row in trials if row["repeat"] == number], names)
            for number in range(1, repeats + 1)
        ]
        report["development_gate"] = promotion_reason(dev["metrics"][REFERENCE], dev["metrics"][challenger], live=live)
        reasons = [promotion_reason(rows[REFERENCE], rows[challenger], live=live) for rows in report["repetitions"]]
        report["holdout_gate"] = reasons
        eligible = {"strict_completion_gain", "token_saving_at_equal_or_better_quality"}
        all_models = {model for group in [dev["metrics"], *report["repetitions"]] for name in names
                      for model in group[name]["resolved_models"]}
        report["model_consistent_across_splits"] = len(all_models) == 1 and "None" not in all_models
        report["promotion_supported"] = (
            report["model_consistent_across_splits"] and report["development_gate"] in eligible
            and len(set(reasons)) == 1 and reasons[0] in eligible
        )
        report["recommended_policy"] = challenger if report["promotion_supported"] else REFERENCE
        _write(directory / "holdout.json", report)
    return report
