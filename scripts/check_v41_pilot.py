"""Prepare/read back a real candidate. This script never approves memory."""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.codex_flow import recall
from repomind.memory.review import ReviewQueue, read_record

ROOT = Path(__file__).resolve().parents[1]
QUOTE = '"accepted_path": "codex_exec_wrapper",'
FIELD = "v4_acceptance_path"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("--db", type=Path, default=ROOT / "work/v4.0/pilot.sqlite3")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("choose a new report path; existing evidence is preserved")
    database = args.db.resolve()
    if not database.is_file():
        raise ValueError("use the existing V4.0 pilot ledger, or explicitly prepare a separate pilot first")
    if args.action == "prepare":
        backup = ROOT / "work/v4.1/pilot-before.sqlite3"
        backup.parent.mkdir(parents=True, exist_ok=True)
        if not backup.exists():
            with sqlite3.connect(database) as source, sqlite3.connect(backup) as target:
                source.backup(target)
        commit = subprocess.check_output(["git", "rev-parse", "v4.0.0^{commit}"], cwd=ROOT).decode().strip()
        artifact = read_record(Path("reports/v4.0/acceptance.json"), commit=commit,
                               repo=ROOT, recorded_at=None, quote=QUOTE)
        with SQLiteMemoryStore(database) as store:
            row, created = ReviewQueue(store).propose(artifact=artifact, quote=QUOTE, project_id="RepoMind",
                subject="codex", predicate=FIELD, value="显式包装器", event_type="declare", effective_at=None)
        output = {"stage_goal":"V4.1 real browser review of RepoMind evidence", "created":created,
                  "candidate":row.model_dump(mode="json"),
                  "before_approval_recall":recall(database,"RepoMind",FIELD),
                  "backup_sha256":hashlib.sha256(backup.read_bytes()).hexdigest()}
        assert not any(fact["source_id"]==row.draft.source_id for fact in output["before_approval_recall"])
        output["new_candidate_hidden_before_approval"] = True
    else:
        with SQLiteMemoryStore(database, read_only=True) as store:
            rows=[row for row in ReviewQueue(store,initialize=False).list("RepoMind",None)
                  if row.draft.subject=="codex" and row.draft.predicate==FIELD]
            assert len(rows)==1
            row=rows[0]
            assert row.status=="confirmed" and row.revision==2 and row.draft.value=="codex_exec_wrapper"
            event=store.get_event(row.event_id)
            assert event.value==row.draft.value
        facts=[fact for fact in recall(database,"RepoMind",FIELD) if fact["field"]==FIELD]
        assert len(facts)==1 and facts[0]["value"]=="codex_exec_wrapper"
        assert facts[0]["source_id"]==row.draft.source_id
        assert recall(database,"OtherProject",FIELD)==[]
        output={"stage_goal":"V4.1 read back browser-approved memory in another process", "passed":True,
                "candidate":row.model_dump(mode="json"), "recalled":facts,"other_project_hidden":True}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x",encoding="utf-8",newline="\n") as stream:
        json.dump(output,stream,ensure_ascii=False,indent=2)
        stream.write("\n")
    print(json.dumps(output,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
