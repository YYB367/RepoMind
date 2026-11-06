"""Two-process RepoMind self-pilot using pinned real artifacts and a dedicated ledger."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

IMPLEMENTATION = "598c7cb71f38d0d75bb0d27821640039fae87eef"
DELIVERY = "53fa686f76195eda7e981bf0751398d4a011d91c"
PROJECT = "RepoMind"
CODE = "src/repomind/agent/loop.py"
REPORT = "reports/v3-recovery/acceptance.json"
CASES = {
    "recovery_reminder": (CODE, IMPLEMENTATION,
                          "append_response(response,include_note=feedback_on_protocol_error and isinstance(exc,ValueError))",
                          "implemented", "complete"),
    "default_strategy": (REPORT, DELIVERY, '"recommended_policy": "reference"', "reference", "declare"),
    "promotion_supported": (REPORT, DELIVERY, '"promotion_supported": false', "false", "declare"),
    "experiment_challenger": (REPORT, DELIVERY, '"challenger": "compact-guided-recovery"',
                               "compact-guided-recovery", "declare"),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=("capture", "verify"))
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.db.resolve() == args.output.resolve():
        raise ValueError("choose a fresh receipt path distinct from the database")
    if args.phase == "capture" and args.db.exists():
        raise ValueError("capture requires a fresh dedicated pilot database")
    args.db.parent.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    commands = []

    def call(*argv, expected_exit=0):
        with subprocess.Popen([sys.executable, "-m", "repomind", "--db", str(args.db), *argv],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, encoding="utf-8") as process:
            stdout, stderr = process.communicate(timeout=30)
            if process.returncode != expected_exit:
                raise RuntimeError(f"pilot command {argv[:2]} failed: {stderr}")
            result = json.loads(stdout if expected_exit == 0 else stderr)
            commands.append({"args": list(argv), "pid": process.pid, "exit": process.returncode, "result": result})
            return result

    def propose(field, draft_value=None):
        path, commit, quote, value, kind = CASES[field]
        return call("review", "propose", path, "--commit", commit, "--project", PROJECT,
                    "--subject", "harness", "--field", field, "--quote", quote,
                    "--value", draft_value or value, "--event-type", kind)

    def query(field, project=PROJECT, *extra):
        as_of = datetime.now(timezone.utc).date().isoformat()
        return call("query", "--project", project, "--subject", "harness", "--field", field,
                    "--as-of", as_of, "--with-sources", *extra)

    if args.phase == "capture":
        ids = {}
        for field in CASES:
            draft = "restored" if field == "recovery_reminder" else None
            proposed = propose(field, draft)
            candidate = proposed["candidate"]
            assert proposed["created"] and candidate["status"] == "pending"
            ids[field] = candidate["candidate_id"]
            assert query(field)["status"] == "unknown"
        cid = ids["recovery_reminder"]
        shown = call("review", "show", cid, "--project", PROJECT)
        assert shown["draft"]["value"] == "restored"
        edited = call("review", "edit", cid, "--project", PROJECT, "--revision", "1", "--value", "implemented")
        assert edited["revision"] == 2
        assert "revision" in call("review", "confirm", cid, "--project", PROJECT, "--revision", "1",
                                   expected_exit=2)["message"]
        confirmed = call("review", "confirm", cid, "--project", PROJECT, "--revision", "2")
        assert confirmed["status"] == "confirmed"
        assert call("review", "confirm", cid, "--project", PROJECT, "--revision", "2") == confirmed
        assert propose("recovery_reminder", "restored") == {"created": False, "candidate": confirmed}
        assert call("review", "confirm", ids["default_strategy"], "--project", PROJECT,
                    "--revision", "1")["status"] == "confirmed"
        assert call("review", "reject", ids["experiment_challenger"], "--project", PROJECT,
                    "--revision", "1")["status"] == "rejected"
    else:
        for field in ("recovery_reminder", "default_strategy"):
            path, commit, quote, value, kind = CASES[field]
            answer = query(field)
            assert answer["status"] == "ok" and answer["value"] == value and len(answer["evidence"]) == 1
            assert answer["evidence"][0]["event_type"] == kind
            source, = answer["sources"]
            artifact = source["artifact"]
            assert (artifact["path"], artifact["commit"]) == (path, commit)
            blob = subprocess.check_output(["git", "--no-replace-objects", "cat-file", "blob", f"{commit}:{path}"])
            assert hashlib.sha256(blob).hexdigest() == artifact["sha256"] and quote in blob.decode("utf-8")
            assert source["record"]["text"] == source["provenance"]["evidence_text"] == quote
            assert query(field, PROJECT, "--known-at", artifact["recorded_at"])["status"] == "unknown"
        for field, project in (("promotion_supported", PROJECT), ("experiment_challenger", PROJECT),
                               ("default_strategy", "OtherProject"), ("recovery_reminder", "OtherProject")):
            result = query(field, project)
            assert result["status"] == "unknown" and result["sources"] == []
        rows = call("review", "list", "--project", PROJECT)["candidates"]
        assert {row["draft"]["predicate"]: row["status"] for row in rows} == {
            "recovery_reminder": "confirmed", "default_strategy": "confirmed",
            "promotion_supported": "pending", "experiment_challenger": "rejected",
        }
        assert all(row["event_id"] is None for row in rows if row["status"] != "confirmed")

    receipt = {"stage_goal": "V3.1 verify real RepoMind memory review across independent processes",
               "kind": "real_project_cli", "phase": args.phase, "session_id": uuid4().hex,
               "parent_pid": os.getpid(), "recorded_at": datetime.now(timezone.utc).isoformat(),
               "model_calls": 0, "passed": True, "commands": commands}
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(f"{args.phase}: {len(commands)} CLI subprocess checks passed, receipt: {args.output}")


if __name__ == "__main__":
    main()
