"""Bounded loopback HTTP adapter around the existing memory/review services."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
import json
from pathlib import Path
import re
import secrets
import sqlite3
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, ValidationError

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.domain.models import Contract, Text
from repomind.memory.review import ReviewQueue
from repomind.workbench import Workbench


class Change(Contract):
    project: Text = Field(max_length=100)
    revision: int = Field(strict=True, ge=1)
    value: Text | None = Field(default=None, max_length=4000)
    event_type: str | None = None
    effective_at: str | None = None


class HTTPError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


class WorkbenchServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, database: Path, port: int = 8765, project: str = "RepoMind"):
        if not 0 <= port <= 65535:
            raise ValueError("port must be between 0 and 65535")
        self.workbench = Workbench(database.resolve())
        self.default_project = project
        self.csrf = secrets.token_urlsafe(32)
        super().__init__(("127.0.0.1", port), Handler)
        self.origin = f"http://127.0.0.1:{self.server_port}"


class Handler(BaseHTTPRequestHandler):
    server_version = "RepoMind"
    sys_version = ""

    def setup(self):
        super().setup()
        self.connection.settimeout(10)

    def log_message(self, *_args):
        # Quotes, query terms and private paths never go to an access log.
        pass

    def send(self, status, body, content_type="application/json; charset=utf-8"):
        raw = (json.dumps(body, ensure_ascii=False).encode("utf-8")
               if content_type.startswith("application/json") else body)
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "img-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.end_headers()
        self.wfile.write(raw)

    def guard(self, write=False):
        if self.headers.get("Host") != self.server.origin.removeprefix("http://"):
            raise HTTPError(403, "请使用启动时显示的 127.0.0.1 地址。")
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise HTTPError(403, "请直接打开本地工作台。")
        if write and (self.headers.get("Origin") != self.server.origin
                      or not secrets.compare_digest(self.headers.get("X-RepoMind-CSRF", ""), self.server.csrf)):
            raise HTTPError(403, "页面授权已失效，请刷新本地工作台后重试。")

    def params(self, allowed):
        parts = urlsplit(self.path)
        if parts.scheme or parts.netloc or len(self.path) > 8192:
            raise HTTPError(400, "请求地址无效。")
        args = parse_qs(parts.query, keep_blank_values=True, max_num_fields=12)
        if args.keys() - allowed or any(len(values) != 1 for values in args.values()):
            raise HTTPError(400, "筛选参数无效。")
        return parts.path, {key: values[0] for key, values in args.items()}

    @staticmethod
    def project(args):
        name = args.get("project", "").strip()
        if not name or len(name) > 100 or any(ord(char) < 32 for char in name):
            raise HTTPError(400, "请填写有效的项目名称。")
        return name

    @staticmethod
    def pagination(args):
        try:
            offset, limit = int(args.get("offset", "0")), int(args.get("limit", "50"))
            if offset < 0 or not 1 <= limit <= 100 or len(args.get("q", "")) > 400:
                raise ValueError()
            return {"offset": offset, "limit": limit, "q": args.get("q", "").strip()}
        except ValueError:
            raise HTTPError(400, "分页或搜索参数超出范围。") from None

    def do_GET(self):
        self.dispatch(False)

    def do_POST(self):
        self.dispatch(True)

    def dispatch(self, write):
        try:
            self.guard(write)
            if write:
                self.mutate()
            else:
                self.read()
        except HTTPError as error:
            self.send(error.status, {"error": error.message})
        except ValidationError:
            self.send(400, {"error": "字段或日期无效；时间须包含时区，正文不能为空。"})
        except ValueError:
            self.send(400, {"error": "请求无效，请检查字段、日期和分页参数。"})
        except sqlite3.Error:
            self.send(503, {"error": "记忆库暂不可用或正在写入，请检查数据库路径并重试。"})
        except OSError:
            self.send(503, {"error": "无法访问本地记忆库或页面文件。"})

    def read(self):
        path, args = self.params({"project", "status", "q", "as_of", "known_at", "offset", "limit"})
        if path in ("/", "/review", "/memories"):
            body = files("repomind.web").joinpath("index.html").read_text(encoding="utf-8")
            body = body.replace("__CSRF__", self.server.csrf)
            self.send(200, body.encode("utf-8"), "text/html; charset=utf-8")
        elif path in ("/static/style.css", "/static/app.js"):
            name = path.rsplit("/", 1)[1]
            content_type = "text/css" if name.endswith(".css") else "text/javascript"
            self.send(200, files("repomind.web").joinpath(name).read_bytes(), content_type + "; charset=utf-8")
        elif path == "/api/projects":
            self.send(200, {"projects": self.server.workbench.projects(),
                            "default_project": self.server.default_project})
        elif path == "/api/candidates":
            project = self.project(args)
            status = args.get("status", "pending")
            if status not in {"pending", "confirmed", "rejected", "all"}:
                raise HTTPError(400, "候选状态无效。")
            self.send(200, self.server.workbench.candidates(project, status=status, **self.pagination(args)))
        elif path == "/api/memories":
            project = self.project(args)
            self.send(200, self.server.workbench.memories(project, as_of=args.get("as_of"),
                          known_at=args.get("known_at"), **self.pagination(args)))
        else:
            raise HTTPError(404, "页面或记录不存在。")

    def mutate(self):
        path, args = self.params(set())
        match = re.fullmatch(r"/api/candidates/(review-[0-9a-f]{64})/(edit|confirm|reject)", path)
        if not match:
            raise HTTPError(404, "审核操作不存在。")
        length = self.headers.get("Content-Length", "")
        if (self.headers.get("Content-Type") != "application/json" or not length.isdecimal()
                or not 0 < int(length) <= 32768 or self.headers.get("Transfer-Encoding")):
            raise HTTPError(400, "请提交不超过 32 KiB 的 JSON 审核请求。")
        try:
            body = json.loads(self.rfile.read(int(length)))
        except (ValueError, UnicodeError):
            raise HTTPError(400, "审核内容不是有效的 JSON。") from None
        change = Change.model_validate(body)
        self.project({"project": change.project})
        cid, action = match.groups()
        edits = change.model_dump(exclude_unset=True, exclude={"project", "revision"})
        if (action != "edit" and edits) or (action == "edit" and (not edits or any(v is None for v in edits.values()))):
            raise HTTPError(400, "请保存有效修改，再确认或拒绝候选。")
        if not self.server.workbench.database.is_file():
            raise HTTPError(404, "尚无候选，请先通过命令行或 Codex 生成。")
        with SQLiteMemoryStore(self.server.workbench.database) as store:
            queue = ReviewQueue(store)
            try:
                queue.show(change.project, cid)
            except ValueError:
                raise HTTPError(404, "当前项目中不存在这条候选。") from None
            try:
                if action == "edit":
                    row = queue.edit(change.project, cid, change.revision, **edits)
                else:
                    row = queue.decide(change.project, cid, change.revision,
                                       decision="confirmed" if action == "confirm" else "rejected")
            except ValueError as error:
                if "revision" in str(error) or "final review" in str(error) or "only pending" in str(error):
                    raise HTTPError(409, "记录已变化，请刷新并重新核对后再审核。") from None
                raise
        self.send(200, row.model_dump(mode="json"))


def add_web_parser(commands):
    parser = commands.add_parser("web", help="Run the local review and project-memory workbench")
    parser.add_argument("--db", type=Path, default=argparse.SUPPRESS)
    parser.add_argument("--project", default="RepoMind", help="Initially selected project")
    parser.add_argument("--port", type=int, default=8765)


def run_web(args):
    try:
        Handler.project({"project": args.project})
    except HTTPError as error:
        raise ValueError(error.message) from None
    with WorkbenchServer(args.db, args.port, args.project.strip()) as server:
        print(f"RepoMind 本地工作台：{server.origin}/review", flush=True)
        print(f"记忆库：{args.db.resolve()}\n按 Ctrl+C 停止。", flush=True)
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass
    return 0
