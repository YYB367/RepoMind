"""Read the frozen example through a real, disposable OpenViking 0.4.21 server."""
import argparse
from contextlib import asynccontextmanager
from importlib.metadata import version
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Thread
from time import monotonic, sleep
from uuid import uuid4

from repomind.context.selection import Corpus


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", required=True, type=Path, help="Parent for a new disposable data directory")
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    corpus_path = project / "data/v2.1/corpus.json"
    corpus = Corpus.load(corpus_path)
    directory = args.work_dir.resolve() / ("openviking-" + uuid4().hex)
    directory.mkdir(parents=True)
    config_path = directory / "ov.conf"
    # A placeholder local model address satisfies startup configuration. Native
    # file fixture seeding and HTTP reads require no model traffic.
    config = {
        "storage": {"workspace": (directory / "data").as_posix()},
        "server": {"host": "127.0.0.1", "auth_mode": "dev"},
        "embedding": {"dense": {"provider": "openai", "api_base": "http://127.0.0.1:1/v1",
                                "api_key": "fixture", "model": "fixture", "dimension": 8}},
    }
    config_path.write_text(json.dumps(config), encoding="utf-8")
    os.environ["OPENVIKING_CONFIG_FILE"] = str(config_path)
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"

    import uvicorn
    from openviking.server.app import create_app
    from openviking.server.dependencies import get_service
    from openviking.server.identity import RequestContext, Role
    from openviking.storage.viking_fs._base import get_viking_fs

    root = "viking://resources/repomind-v21"
    app = create_app(config_path=str(config_path))
    original = app.router.lifespan_context

    @asynccontextmanager
    async def seeded_lifespan(app):
        async with original(app):
            filesystem = get_viking_fs()
            context = RequestContext(user=get_service().user, role=Role.ADMIN)
            for project_id, groups in corpus.projects.items():
                for group in groups:
                    uri = f"{root}/{project_id}/{group.id}"
                    await filesystem.mkdir(uri, exist_ok=True, ctx=context)
                    await filesystem.write_file(uri + "/.abstract.md", group.abstract, ctx=context)
                    await filesystem.write_file(uri + "/.overview.md", group.overview, ctx=context)
                    for doc in group.documents:
                        await filesystem.write_file(uri + "/" + doc.id + ".md", doc.body, ctx=context)
            yield

    app.router.lifespan_context = seeded_lifespan
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, access_log=False, log_level="warning"))
        thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            deadline = monotonic() + 40
            while not server.started and thread.is_alive() and monotonic() < deadline:
                sleep(0.05)
            if not server.started:
                raise RuntimeError("OpenViking did not start")
            results = []
            env = {**os.environ, "REPOMIND_OPENVIKING_URL": f"http://127.0.0.1:{port}",
                   "REPOMIND_OPENVIKING_KEY": ""}
            for project_id, expected in (("cedar-api", "12 minutes"), ("pine-api", "7 minute")):
                command = [sys.executable, "-m", "repomind", "context-select", "--corpus", str(corpus_path),
                           "--project", project_id, "--query", "production canary observation window",
                           "--budget", "640", "--openviking-root", root]
                execution = subprocess.run(command, cwd=directory, env=env, capture_output=True,
                                           encoding="utf-8", timeout=25, check=True)
                output = json.loads(execution.stdout)
                assert output["backend"] == "openviking"
                assert output["project"] == project_id and output["evidence_bytes"] <= 640
                assert {visit["level"] for visit in output["visits"]} == {"L0", "L1", "L2"}
                first = output["evidence"][0]
                assert first["source_id"] == "canary" and expected in first["text"]
                results.append(output)
        finally:
            server.should_exit = True
            thread.join(timeout=15)
        if thread.is_alive():
            raise RuntimeError("OpenViking smoke server did not stop")
    print(json.dumps({
        "stage_goal": "V2.1 verify the three native content routes on loopback",
        "server_version": version("openviking"), "passed": True, "server_stopped": True,
        "storage": "native RAGFS with curated fixture summaries", "models_called": False,
        "authentication": "loopback dev mode", "cases": results,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
