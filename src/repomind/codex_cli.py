"""CLI entry points for native hooks and the explicit Codex exec wrapper."""
import argparse
import base64
import json
import os
from pathlib import Path
import shlex
import shutil
import sqlite3
import subprocess
import sys

from repomind.codex_flow import CAPTURE_GUIDANCE, EVENTS, MARKER, capture, hook, recall, recall_context
from repomind.intelligence.providers import _json_loads
from repomind.codex_activity import ActivityLog


def codex_executable():
    """Resolve once per invocation so Desktop upgrades do not strand PATH."""
    configured = os.environ.get("REPOMIND_CODEX_EXECUTABLE")
    if configured:
        path = Path(configured)
        if not path.is_absolute() or not path.is_file():
            raise ValueError("REPOMIND_CODEX_EXECUTABLE 必须指向存在的程序绝对路径。")
        return str(path)
    found = shutil.which("codex")
    if found:
        return found
    local_data = os.environ.get("LOCALAPPDATA")
    if os.name == "nt" and local_data:
        desktop_bin = Path(local_data) / "OpenAI" / "Codex" / "bin"
        candidates = list(desktop_bin.glob("*/codex.exe"))
        candidates = [path for path in candidates if path.is_file()]
        if candidates:
            return str(max(candidates, key=lambda path: path.stat().st_mtime))
    raise ValueError("未找到 Codex。请安装 CLI，或设置 REPOMIND_CODEX_EXECUTABLE 为程序绝对路径。")


def add_codex_parser(commands):
    parser = commands.add_parser("codex", help="Connect Codex sessions to reviewed project memory")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--project", required=True)
    parser.add_argument("--db", type=Path, default=argparse.SUPPRESS)
    actions = parser.add_subparsers(dest="codex_action", required=True)
    run = actions.add_parser("run", help="Explicit fallback: start a new codex exec session")
    run.add_argument("--prompt", required=True)
    run.add_argument("--receipt", type=Path)
    run.add_argument("--workspace-write", action="store_true", help="Request Codex's workspace-write sandbox")
    native = actions.add_parser("hooks-config", help="Generate an opt-in project hooks file")
    native.add_argument("--output", type=Path, required=True)
    native.add_argument("--audit", type=Path)
    event = actions.add_parser("hook", help="Read a Codex hook event from stdin")
    event.add_argument("--audit", type=Path)
    read = actions.add_parser("recall", help="Inspect which approved facts match a task")
    read.add_argument("--prompt", required=True)


def _write_new(path, body):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(body, ensure_ascii=False, indent=2) + "\n")


def _hooks_config(root, database, project, audit):
    bootstrap = root / "scripts" / "repomind_codex_hook.py"
    entry = [str(bootstrap)] if bootstrap.is_file() else ["-m", "repomind"]
    argv = [sys.executable, *entry, "--db", str(database), "codex",
            "--root", str(root), "--project", project, "hook"]
    if audit:
        argv += ["--audit", str(audit.resolve())]
    windows = "& " + " ".join("'" + arg.replace("'", "''") + "'" for arg in argv)
    windows_cmd = "powershell.exe -NoProfile -NonInteractive -EncodedCommand " + base64.b64encode(
        windows.encode("utf-16le")
    ).decode("ascii")
    handler = {"type": "command", "command": shlex.join(argv), "commandWindows": windows_cmd, "timeout": 25}
    return {"hooks": {name: [{"hooks": [handler]}] for name in EVENTS}}


def _run(root, database, project, prompt, *, workspace_write=False, facts_override=None, runner=None):
    facts = recall(database, project, prompt) if facts_override is None else facts_override
    parts = [prompt, CAPTURE_GUIDANCE]
    if facts:
        parts.append(recall_context(project, facts))
    argv = [codex_executable(), "exec", "--json", "-C", str(root)]
    if workspace_write:
        argv.extend(["--sandbox", "workspace-write"])
    try:
        child = (runner or subprocess.run)(
            [*argv, "-"],
            input="\n\n".join(parts), encoding="utf-8", errors="replace", capture_output=True, timeout=1800,
        )
    except subprocess.TimeoutExpired:
        raise ValueError("codex exec did not finish within 30 minutes") from None
    if child.returncode:
        diagnostic = child.stderr + child.stdout
        reason = next((label for token, label in (
            ("CODEX_HOME", "Codex profile is unavailable"),
            ("not logged in", "Codex login is required"),
            ("401", "Codex authentication failed"),
            ("429", "Codex reported a usage limit"),
            ("websocket", "Codex network transport failed"),
        ) if token in diagnostic), "inspect codex exec in the same environment")
        raise ValueError(f"codex exec exited {child.returncode}: {reason}")
    thread_id = None
    message = None
    completed = False
    usage = []
    tool_errors = []
    activity = ActivityLog()
    for line in child.stdout.splitlines():
        if not line.strip():
            continue
        event = _json_loads(line)
        activity.observe(event)
        if event.get("type") == "thread.started":
            thread_id = event.get("thread_id")
        elif event.get("type") == "item.completed":
            item = event.get("item", {})
            if item.get("type") == "agent_message":
                message = item.get("text")
            if item.get("type") == "command_execution" and item.get("exit_code") not in (None, 0):
                tool_errors.append({"type": "command_execution", "exit_code": item["exit_code"]})
        elif event.get("type") == "turn.completed":
            completed = True
            if isinstance(event.get("usage"), dict):
                usage.append(event["usage"])
    if not completed or not isinstance(thread_id, str) or not isinstance(message, str):
        raise ValueError("codex exec did not produce a completed session and final message")
    try:
        captured = capture(root, database, project, message)
    except ValueError:
        captured = {"pending_ids": [], "created": 0, "capture_error": "invalid proposal block"}
    return {"mode": "codex_exec_wrapper", "session_id": thread_id,
            "recalled": facts, "capture": captured, "assistant_message": MARKER.sub("", message).rstrip(),
            "usage": usage, "tool_errors": tool_errors, "activity": activity.view()}


def run_codex(args):
    root = args.root.resolve()
    database = args.db.resolve()
    project = args.project.strip()
    if not root.is_dir() or not project or len(project) > 100 or any(ord(c) < 32 for c in project):
        raise ValueError("Codex flow requires an existing root and a valid project")
    if args.codex_action == "hooks-config":
        output = args.output.resolve()
        if output == database or not output.is_relative_to(root) or output.suffix != ".json":
            raise ValueError("hook configuration must be a separate JSON file inside the project")
        output.parent.mkdir(parents=True, exist_ok=True)
        _write_new(output, _hooks_config(root, database, project, args.audit))
        return {"config": str(output), "mode": "native_hooks_config"}
    if args.codex_action == "hook":
        try:
            body = sys.stdin.buffer.read(262145)
            if len(body) > 262144:
                raise ValueError("hook event is too large")
            payload = _json_loads(body)
            if not isinstance(payload, dict):
                raise ValueError("hook event must be an object")
            output, receipt = hook(root, database, project, payload)
            if receipt is not None and args.audit is not None:
                if args.audit.resolve() == database:
                    raise ValueError("audit path must be separate from ledger")
                args.audit.parent.mkdir(parents=True, exist_ok=True)
                with args.audit.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(receipt, ensure_ascii=False) + "\n")
            return output
        except (OSError, ValueError, sqlite3.Error):
            return {"systemMessage": "RepoMind hook could not access or validate its local inputs."}
    if args.codex_action == "recall":
        return {"project": project, "facts": recall(database, project, args.prompt)}
    if args.receipt and (args.receipt.exists() or args.receipt.resolve() == database):
        raise ValueError("choose a fresh receipt path separate from the ledger")
    result = _run(root, database, project, args.prompt, workspace_write=args.workspace_write)
    if args.receipt:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        _write_new(args.receipt, result)
    return result
