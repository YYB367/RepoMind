import json,sqlite3
import pytest
from repomind.source_lookup import source_lookup
def setup(status='confirmed',body='{"text":"evidence"}'):
    db=sqlite3.connect(':memory:');db.executescript('CREATE TABLE nl_sources(project_id,source_id,source_json); CREATE TABLE memory_review_candidates(project_id,status,candidate_json);')
    db.execute('INSERT INTO nl_sources VALUES (?,?,?)',('RepoMind','s',body));db.execute('INSERT INTO memory_review_candidates VALUES (?,?,?)',('RepoMind',status,json.dumps({'draft':{'source_id':'s'}})));db.commit();return db
def test_rejected_and_foreign_review():
    assert source_lookup(setup('rejected'),'RepoMind','s') is None
    db=setup();db.execute("UPDATE memory_review_candidates SET project_id='Other'");assert source_lookup(db,'RepoMind','s') is None
def test_literal_sql_parameters():
    db=setup();assert source_lookup(db,"RepoMind' OR 1=1 --",'s') is None
    assert source_lookup(db,'RepoMind',"s' OR 1=1 --") is None
def test_missing_and_read_only_transaction():
    db=sqlite3.connect(':memory:');assert source_lookup(db,'RepoMind','s') is None
    db=setup();db.execute('BEGIN');db.execute('PRAGMA query_only=ON');before=db.total_changes
    assert source_lookup(db,'RepoMind','s')=={'text':'evidence'} and db.in_transaction and db.total_changes==before
def test_invalid_source_and_scope():
    for body in ['[]','not-json','null']:
        with pytest.raises(ValueError): source_lookup(setup(body=body),'RepoMind','s')
    for project,sid in [('', 's'),('RepoMind',None),(True,'s')]:
        with pytest.raises(ValueError): source_lookup(setup(),project,sid)
