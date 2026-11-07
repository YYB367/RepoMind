import json,sqlite3
from repomind.source_lookup import source_lookup
def setup(status='confirmed'):
    db=sqlite3.connect(':memory:');db.executescript('CREATE TABLE nl_sources(project_id,source_id,source_json); CREATE TABLE memory_review_candidates(project_id,status,candidate_json);')
    db.execute('INSERT INTO nl_sources VALUES (?,?,?)',('RepoMind','s',json.dumps({'text':'evidence'})))
    db.execute('INSERT INTO memory_review_candidates VALUES (?,?,?)',('RepoMind',status,json.dumps({'draft':{'source_id':'s'}})));db.commit();return db
def test_confirmed():
    assert source_lookup(setup(),'RepoMind','s')=={'text':'evidence'}
def test_pending_and_project():
    assert source_lookup(setup('pending'),'RepoMind','s') is None
    assert source_lookup(setup(),'Other','s') is None
