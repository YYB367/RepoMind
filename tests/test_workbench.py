"""Exercise real HTTP boundaries and shared ledger rules, using isolated records."""
from contextlib import contextmanager
from http.client import HTTPConnection
import json
import threading

import pytest

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.cli import main
from repomind.codex_flow import recall
from repomind.domain.models import Event
from repomind.memory.review import ReviewQueue, read_record
from repomind.web.server import WorkbenchServer
from repomind.workbench import Workbench

STAMP = "2020-01-01T00:00:00Z"


@contextmanager
def serving(database):
    with WorkbenchServer(database, 0) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(5)


def request(server, path, body=None, *, method=None, headers=None, trusted=True):
    h = {"Host": server.origin.removeprefix("http://")}
    if body is not None:
        h["Content-Type"] = "application/json"
        if trusted:
            h.update({"Origin": server.origin, "X-RepoMind-CSRF": server.csrf})
    h.update(headers or {})
    client = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    client.request(method or ("POST" if body is not None else "GET"), path,
                   json.dumps(body, ensure_ascii=False).encode() if body is not None else None, h)
    response = client.getresponse()
    raw = response.read()
    content_type = response.getheader("Content-Type")
    result = json.loads(raw) if content_type.startswith("application/json") else raw.decode()
    status, response_headers = response.status, dict(response.getheaders())
    client.close()
    return status, result, response_headers


def propose(database, source, *, project="RepoMind", field="default_strategy", value="draft"):
    with SQLiteMemoryStore(database) as store:
        artifact = read_record(source, commit=None, repo=source.parent, recorded_at=STAMP, quote="reference")
        row, _ = ReviewQueue(store).propose(artifact=artifact, quote="reference", project_id=project,
            subject="harness", predicate=field, value=value, event_type="declare", effective_at=None)
        return row


@pytest.fixture
def ledger(tmp_path):
    database = tmp_path / "ledger.sqlite3"
    source = tmp_path / "source.md"
    source.write_text("default strategy is reference. <img src=x onerror=alert(1)>\n", encoding="utf-8")
    return database, source


def test_http_edit_confirm_cli_and_recall_share_one_ledger(ledger, capsys):
    database, source = ledger
    row = propose(database, source)
    base = f"/api/candidates/{row.candidate_id}"
    with serving(database) as server:
        assert request(server, "/api/memories?project=RepoMind")[1]["total"] == 0
        edit = {"project":"RepoMind", "revision":1, "value":"reference"}
        status, edited, _ = request(server, base + "/edit", edit)
        assert status == 200 and edited["revision"] == 2
        assert request(server, base + "/confirm", {"project":"RepoMind", "revision":1})[0] == 409
        assert recall(database, "RepoMind", "default_strategy") == []
        approved = request(server, base + "/confirm", {"project":"RepoMind", "revision":2})
        assert approved[0] == 200 and approved[1]["status"] == "confirmed"
        assert request(server, base + "/confirm", {"project":"RepoMind", "revision":2})[1] == approved[1]
        assert request(server, base + "/reject", {"project":"RepoMind", "revision":2})[0] == 409
        memory = request(server, "/api/memories?project=RepoMind&q=reference&as_of=2020-01-01")[1]
        assert memory["total"] == 1 and memory["items"][0]["value"] == "reference"
        assert memory["items"][0]["sources"][0]["artifact"]["sha256"] == row.artifact.sha256
        assert request(server, "/api/memories?project=RepoMind&known_at=2020-01-01")[1]["items"] == []
    assert main(["--db",str(database),"review","show",row.candidate_id,"--project","RepoMind"]) == 0
    assert json.loads(capsys.readouterr().out)["status"] == "confirmed"
    assert recall(database,"RepoMind","default_strategy")[0]["value"] == "reference"
    with SQLiteMemoryStore(database) as store:
        assert store.count() == 1


def test_rejection_and_project_scope_cannot_be_bypassed(ledger):
    database, source = ledger
    row = propose(database, source)
    other = propose(database, source, project="OtherProject", value="private")
    base = f"/api/candidates/{row.candidate_id}"
    with serving(database) as server:
        assert request(server, base+"/confirm", {"project":"OtherProject","revision":1})[0] == 404
        assert request(server, base+"/reject", {"project":"RepoMind","revision":1})[1]["status"] == "rejected"
        assert request(server, base+"/confirm", {"project":"RepoMind","revision":1})[0] == 409
        listing = request(server,"/api/candidates?project=RepoMind&status=all")[1]
        assert listing["total"] == 1 and listing["items"][0]["candidate_id"] != other.candidate_id
        assert request(server,"/api/memories?project=RepoMind")[1]["total"] == 0
        assert request(server,"/api/memories?project=OtherProject")[1]["total"] == 0
    assert recall(database,"OtherProject","default_strategy") == []


@pytest.mark.parametrize("headers,trusted", [({},False), ({"Origin":"https://example.test"},True),
    ({"X-RepoMind-CSRF":"wrong"},True), ({"Host":"attacker.test"},True),
    ({"Sec-Fetch-Site":"cross-site"},True)])
def test_browser_write_requires_local_origin_and_page_token(ledger, headers, trusted):
    database, source = ledger
    row=propose(database,source)
    with serving(database) as server:
        status, _, _ = request(server,f"/api/candidates/{row.candidate_id}/confirm",
            {"project":"RepoMind","revision":1},headers=headers,trusted=trusted)
        assert status == 403
    with SQLiteMemoryStore(database,read_only=True) as store:
        assert store.count() == 0


def test_empty_read_does_not_create_or_migrate_database(tmp_path):
    database=tmp_path / "missing.sqlite3"
    with serving(database) as server:
        assert request(server,"/api/projects")[1]["projects"] == []
        assert request(server,"/api/candidates?project=RepoMind")[1]["items"] == []
        assert request(server,"/api/memories?project=RepoMind")[1]["items"] == []
    assert not database.exists()


def test_http_validation_static_pages_and_read_boundaries(ledger):
    database, source = ledger
    row=propose(database,source)
    with serving(database) as server:
        for path in ("/review","/memories"):
            status, html, headers=request(server,path)
            assert status==200 and server.csrf in html and "frame-ancestors 'none'" in headers["Content-Security-Policy"]
            assert "reference" not in html and "<img src=x" not in html
        assert request(server,"/static/app.js")[0]==200
        assert request(server,"/static/../../source.md")[0]==404
        assert request(server,"/api/candidates")[0]==400
        assert request(server,"/api/candidates?project=A&project=B")[0]==400
        assert request(server,"/api/candidates?project=A&limit=999")[0]==400
        assert request(server,"/api/memories?project=A&as_of=invalid")[0]==400
        assert request(server,"/api/projects",headers={"Host":"evil.test"})[0]==403
        base=f"/api/candidates/{row.candidate_id}"
        assert request(server,base+"/edit",{"project":"RepoMind","revision":1,"value":""})[0]==400
        assert request(server,base+"/confirm",{"project":"RepoMind","revision":True})[0]==400
        assert request(server,base+"/confirm",{"project":"RepoMind","revision":1,"value":"silent edit"})[0]==400
        assert request(server,base+"/edit",{"project":"RepoMind","revision":1,"effective_at":None})[0]==400


def test_temporal_projection_plans_conflicts_and_pagination(ledger):
    database, source = ledger
    with SQLiteMemoryStore(database) as store:
        store.import_events([
            Event(event_id="old",project_id="RepoMind",subject="db",predicate="engine",value="SQLite",
                  event_type="declare",observed_at=STAMP,source_id="s1"),
            Event(event_id="new",project_id="RepoMind",subject="db",predicate="engine",value="Postgres",
                  event_type="complete",observed_at="2021-01-01T00:00:00Z",source_id="s2"),
            Event(event_id="plan",project_id="RepoMind",subject="ui",predicate="launch",value="browser",
                  event_type="plan",observed_at=STAMP,effective_at="2030-01-01T00:00:00Z",source_id="s3"),
            Event(event_id="conflict",project_id="RepoMind",subject="db",predicate="engine",value="MySQL",
                  event_type="declare",observed_at="2021-01-01T00:00:00Z",source_id="s4"),
        ])
    service=Workbench(database)
    old=service.memories("RepoMind",q="engine",as_of="2020-01-01")
    assert old["items"][0]["value"]=="SQLite"
    new=service.memories("RepoMind",q="engine",as_of="2022-01-01")
    assert new["items"][0]["status"]=="insufficient_evidence"
    assert len(new["items"][0]["sources"])==2
    plans=service.memories("RepoMind",q="browser",as_of="2020-01-01")
    assert plans["items"][0]["value"] is None and plans["items"][0]["reason"]=="only_plans"
    assert service.memories("RepoMind",as_of="2019-01-01")["items"]==[]
    first=service.memories("RepoMind",limit=1)
    second=service.memories("RepoMind",offset=1,limit=1)
    assert first["total"]==2 and first["items"][0]["subject"]!=second["items"][0]["subject"]
    assert service.projects()==["RepoMind"]
