"""Author the new, explicitly constructed RepoMind maintenance benchmark once."""
import hashlib
import json
from pathlib import Path
import subprocess
import textwrap

from repomind.agent.models import AgentBudget
from repomind.agent.workspace import digest

ROOT=Path(__file__).resolve().parents[1]
SUITE=ROOT/"data/v4.2"


def code(value):
    return textwrap.dedent(value).strip()+"\n"


def write(path,body):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open("x",encoding="utf-8",newline="\n") as stream:
        stream.write(body)


def json_text(value):
    return json.dumps(value,ensure_ascii=False,indent=2)+"\n"


TASKS=[
    ("dev-key","maint_keys","explicit_key","codex.v4_acceptance_path",
     "Extract the one explicit ASCII subject.field key from a string. Each component starts with a letter then letters/digits/underscore. Do not match inside longer ASCII dotted/identifier strings. Preserve case. Repeated identical keys count once; zero or multiple distinct keys return None. Non-string input raises ValueError. Return a tuple (subject, field) when unique.",
     r'''
     import re
     def explicit_key(text):
         if not isinstance(text,str):
             raise ValueError('text required')
         found=set(re.findall(r'(?<![A-Za-z0-9_.])([A-Za-z][A-Za-z0-9_]*)\.([A-Za-z][A-Za-z0-9_]*)(?![A-Za-z0-9_]|\.[A-Za-z0-9_])',text))
         return next(iter(found)) if len(found)==1 else None
     ''',
     '''
     from repomind.maint_keys import explicit_key
     def test_one_key():
         assert explicit_key('Use codex.v4_acceptance_path.')==('codex','v4_acceptance_path')
     def test_ambiguous():
         assert explicit_key('codex.path and harness.policy') is None
     ''',
     '''
     import pytest
     from repomind.maint_keys import explicit_key
     def test_punctuation_and_unicode():
         assert explicit_key('请查`codex.v4_acceptance_path`。')==('codex','v4_acceptance_path')
     def test_non_text():
         for value in [None,True,1,[],{}]:
             with pytest.raises(ValueError): explicit_key(value)
     def test_longer_tokens():
         for text in ['a.b.c','9a.b','_a.b','a.9b','a.b_ignored.more','no key']:
             assert explicit_key(text) is None
     def test_unique_and_case():
         assert explicit_key('A.b A.b')==('A','b')
         assert explicit_key('A.b a.b') is None
     '''),
    ("dev-citation","citation_view","citation_view","codex.v4_acceptance_path",
     "Validate and return a new citation dict containing only source_id, path, sha256, commit. Input must be a dict. source_id/path are nonblank strings, sha256 is exactly 64 lowercase hexadecimal characters, commit is None/absent or a full 40/64 lowercase hexadecimal ID. Preserve literal strings, ignore extra fields, do not mutate input or read the filesystem. Invalid input raises ValueError.",
     '''
     import re
     def citation_view(fact):
         if not isinstance(fact,dict): raise ValueError('dict required')
         for key in ('source_id','path'):
             if not isinstance(fact.get(key),str) or not fact[key].strip(): raise ValueError('citation required')
         sha=fact.get('sha256'); commit=fact.get('commit')
         if not isinstance(sha,str) or re.fullmatch('[0-9a-f]{64}',sha) is None: raise ValueError('invalid hash')
         if commit is not None and (not isinstance(commit,str) or re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}',commit) is None): raise ValueError('invalid commit')
         return {key:fact.get(key) for key in ('source_id','path','sha256','commit')}
     ''',
     '''
     from repomind.citation_view import citation_view
     def test_literal_source():
         f={'source_id':'review-source-one','path':'reports/v4.0/acceptance.json','sha256':'a'*64}
         assert citation_view(f)==dict(f,commit=None)
     def test_bad_hash():
         import pytest
         with pytest.raises(ValueError): citation_view({'source_id':'s','path':'p','sha256':'short'})
     ''',
     '''
     import pytest
     from repomind.citation_view import citation_view
     def base(): return {'source_id':'s','path':'p','sha256':'b'*64,'commit':'c'*40}
     def test_full_commits_and_extra():
         f=base();f['commit']='f'*64;f['other']={'secret':'not a real key'}
         r=citation_view(f);assert set(r)=={'source_id','path','sha256','commit'} and r['commit']=='f'*64
     def test_invalid_fields():
         for key,value in [('source_id',' '),('path',None),('sha256','A'*64),('commit',True),('commit','d'*41)]:
             f=base();f[key]=value
             with pytest.raises(ValueError): citation_view(f)
     def test_literal_and_no_mutation():
         f=base();f['path']='资料/<tag>.md';r=citation_view(f);r['path']='elsewhere';assert f['path']=='资料/<tag>.md'
     def test_non_dict_and_missing():
         for f in [None,[],{},True]:
             with pytest.raises(ValueError): citation_view(f)
     '''),
    ("dev-clock","query_clock","query_clock","harness.recovery_acceptance_recommendation",
     "Implement query_clock(as_of, known_at=None, *, now). Return {'as_of': aware UTC datetime, 'known_at': aware UTC datetime}. Validate now as an aware timestamp even when both other inputs are supplied. Only None or empty string default to now. Other values use repomind.domain.models.parse_timestamp(..., allow_date=True): a date means UTC end of day, offsets normalize to UTC, implicit local time and numeric/bool inputs raise ValueError. Do not use the wall clock.",
     '''
     from repomind.domain.models import parse_timestamp
     def query_clock(as_of,known_at=None,*,now):
         current=parse_timestamp(now)
         def parse(value):
             return current if value is None or value=='' else parse_timestamp(value,allow_date=True)
         return {'as_of':parse(as_of),'known_at':parse(known_at)}
     ''',
     '''
     from repomind.query_clock import query_clock
     def test_default():
         r=query_clock(None,now='2026-11-07T01:00:00Z');assert r['as_of']==r['known_at']
     def test_date():
         r=query_clock('2026-11-06',now='2026-11-07T01:00:00Z');assert r['as_of'].isoformat()=='2026-11-06T23:59:59.999999+00:00'
     ''',
     '''
     import pytest
     from repomind.query_clock import query_clock
     def test_offset():
         r=query_clock('2026-11-07T08:00:00+08:00','2026-11-06',now='2026-11-07T01:00:00Z')
         assert r['as_of'].hour==0 and r['known_at'].day==6
     def test_implicit_and_numeric():
         for v in [False,0,1.5,'2026-11-07T00:00:00','bad']:
             with pytest.raises(ValueError): query_clock(v,now='2026-11-07T01:00:00Z')
     def test_empty_and_explicit_known():
         r=query_clock('',known_at='2020-01-01',now='2026-11-07T01:00:00Z');assert r['as_of'].year==2026 and r['known_at'].year==2020
     def test_always_validate_now():
         with pytest.raises(ValueError): query_clock('2020-01-01','2021-01-01',now='2026-11-07T00:00:00')
     '''),
    ("hold-review","review_request","review_identity","harness.recovery_acceptance_recommendation",
     "Implement review_identity(body, *, project). Require a dict with exactly project, candidate_id, revision. The explicit project is a nonblank string and must equal body['project'] literally (case and spaces matter). candidate_id is 'review-' plus exactly 64 lowercase hex digits; revision is a plain int >=1 excluding bool. Return (candidate_id, revision). Any invalid input raises ValueError. Do not mutate body.",
     '''
     import re
     def review_identity(body,*,project):
         if not isinstance(project,str) or not project.strip(): raise ValueError('project required')
         if not isinstance(body,dict) or set(body)!={'project','candidate_id','revision'}: raise ValueError('fields required')
         if body['project']!=project: raise ValueError('project mismatch')
         cid=body['candidate_id']; rev=body['revision']
         if not isinstance(cid,str) or re.fullmatch('review-[0-9a-f]{64}',cid) is None: raise ValueError('invalid id')
         if type(rev) is not int or rev<1: raise ValueError('invalid revision')
         return cid,rev
     ''',
     '''
     import pytest
     from repomind.review_request import review_identity
     def test_valid():
         cid='review-'+'a'*64;assert review_identity({'project':'RepoMind','candidate_id':cid,'revision':2},project='RepoMind')==(cid,2)
     def test_scope():
         with pytest.raises(ValueError): review_identity({'project':'Other','candidate_id':'review-'+'a'*64,'revision':1},project='RepoMind')
     ''',
     '''
     import pytest
     from repomind.review_request import review_identity
     def base(): return {'project':'RepoMind','candidate_id':'review-'+'a'*64,'revision':1}
     def test_strict_revisions():
         for rev in [True,False,0,-1,1.0,'1',None]:
             d=base();d['revision']=rev
             with pytest.raises(ValueError): review_identity(d,project='RepoMind')
     def test_shape_and_no_mutation():
         d=base();before=dict(d);review_identity(d,project='RepoMind');assert d==before
         for d in [None,[],dict(base(),value='edit'),{'project':'RepoMind'}]:
             with pytest.raises(ValueError): review_identity(d,project='RepoMind')
     def test_bad_id():
         for cid in ['review-'+'A'*64,'review-'+'a'*63,'review-'+'a'*65,'x',True]:
             d=base();d['candidate_id']=cid
             with pytest.raises(ValueError): review_identity(d,project='RepoMind')
     def test_literal_project():
         for project in ['repomind','RepoMind ','',None,' ']:
             with pytest.raises(ValueError): review_identity(base(),project=project)
     '''),
    ("hold-pack","context_pack","pack_facts","codex.v4_acceptance_path",
     "Implement pack_facts(facts, max_bytes). max_bytes must be a plain int >=2, excluding bool. facts must be a list of dicts, each with nonblank string source_id and path and entirely JSON serializable with nonfinite numbers forbidden. Validate ALL entries even if some are oversized. Walk in input order: include an entire fact if the resulting list encoded by json.dumps(ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8') fits the budget, otherwise skip and continue to later facts. Never truncate citation fields. Return independent copies; do not mutate input. Invalid inputs raise ValueError.",
     '''
     import json
     from copy import deepcopy
     def pack_facts(facts,max_bytes):
         if type(max_bytes) is not int or max_bytes<2 or not isinstance(facts,list): raise ValueError('invalid budget or facts')
         def encode(value): return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
         for fact in facts:
             if not isinstance(fact,dict) or any(not isinstance(fact.get(k),str) or not fact[k].strip() for k in ('source_id','path')): raise ValueError('source required')
             try: encode(fact)
             except (ValueError,TypeError,UnicodeError): raise ValueError('invalid JSON fact') from None
         chosen=[]
         for fact in facts:
             if len(encode(chosen+[fact]))<=max_bytes: chosen.append(deepcopy(fact))
         return chosen
     ''',
     '''
     from repomind.context_pack import pack_facts
     def test_whole_fact():
         f={'source_id':'s','path':'p','value':'x'};assert pack_facts([f],1000)==[f]
     def test_small_budget():
         assert pack_facts([{'source_id':'s','path':'p'}],2)==[]
     ''',
     '''
     import json
     import pytest
     from repomind.context_pack import pack_facts
     def test_utf8_and_exact_limit():
         f={'source_id':'s','path':'中文','value':'记忆'}
         size=len(json.dumps([f],ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8'))
         assert pack_facts([f],size)==[f] and pack_facts([f],size-1)==[]
     def test_skip_and_continue():
         big={'source_id':'big','path':'p','value':'x'*500};small={'source_id':'s','path':'p'}
         assert pack_facts([big,small],70)==[small]
     def test_all_validation():
         for budget in [True,1,-1,2.0,'2']:
             with pytest.raises(ValueError): pack_facts([],budget)
         for fact in [None,{'source_id':'s'},{'source_id':'s','path':'p','x':float('nan')}]:
             with pytest.raises(ValueError): pack_facts([fact],2)
     def test_clones_and_citations():
         f={'source_id':'s','path':'p','sha256':'a'*64,'extra':{'x':[1]}};r=pack_facts([f],1000)
         assert r[0]['sha256']=='a'*64;r[0]['extra']['x'].append(2);assert f['extra']['x']==[1]
     '''),
    ("hold-window","review_window","confirmed_window","harness.recovery_acceptance_recommendation",
     "Implement confirmed_window(records, project, start, end). records is a list of dicts; project is a nonblank string. Bounds accept aware ISO timestamps/datetimes or dates; start date means UTC start of day, end date UTC end of day, both inclusive. Use repomind.domain.models.parse_timestamp and reject reversed bounds. Ignore other projects and statuses except literal confirmed before checking their remaining fields. Matching confirmed records require nonblank candidate_id and timezone-aware reviewed_at timestamp (not a date). Return independent copies in input order whose reviewed_at falls in the range. Invalid inputs or matching records raise ValueError. Do not mutate input.",
     r'''
     from copy import deepcopy
     from datetime import date,datetime
     import re
     from repomind.domain.models import parse_timestamp
     def confirmed_window(records,project,start,end):
         if not isinstance(records,list) or not isinstance(project,str) or not project.strip(): raise ValueError('invalid inputs')
         low=parse_timestamp(start,allow_date=True);high=parse_timestamp(end,allow_date=True)
         if (isinstance(start,date) and not isinstance(start,datetime)) or (isinstance(start,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',start)):
             low=low.replace(hour=0,minute=0,second=0,microsecond=0)
         if low>high: raise ValueError('reversed range')
         chosen=[]
         for row in records:
             if not isinstance(row,dict): raise ValueError('record must be dict')
             if row.get('project_id')!=project or row.get('status')!='confirmed': continue
             if not isinstance(row.get('candidate_id'),str) or not row['candidate_id'].strip(): raise ValueError('candidate required')
             when=parse_timestamp(row.get('reviewed_at'))
             if low<=when<=high: chosen.append(deepcopy(row))
         return chosen
     ''',
     '''
     from repomind.review_window import confirmed_window
     def row(**kw): return dict(project_id='RepoMind',status='confirmed',candidate_id='c',reviewed_at='2026-11-07T00:00:00Z',**kw)
     def test_date_start_inclusive():
         r=row();assert confirmed_window([r],'RepoMind','2026-11-07','2026-11-07')==[r]
     def test_other_status_ignored():
         assert confirmed_window([{'project_id':'Other','status':'confirmed'},{'project_id':'RepoMind','status':'pending'}],'RepoMind','2026-11-07','2026-11-07')==[]
     ''',
     '''
     import pytest
     from repomind.review_window import confirmed_window
     def row(when): return {'project_id':'RepoMind','status':'confirmed','candidate_id':'c','reviewed_at':when}
     def test_timezone_and_edges():
         a=row('2026-11-07T08:00:00+08:00');b=row('2026-11-07T23:59:59.999999Z');c=row('2026-11-08T00:00:00Z')
         assert confirmed_window([a,b,c],'RepoMind','2026-11-07','2026-11-07')==[a,b]
     def test_precise_timestamp_range():
         a=row('2026-11-07T03:00:00Z');b=row('2026-11-07T04:00:00Z')
         assert confirmed_window([a,b],'RepoMind','2026-11-07T03:00:00Z','2026-11-07T03:00:00Z')==[a]
     def test_invalid_bounds_and_records():
         for lo,hi in [('2026-11-08','2026-11-07'),('2026-11-07T00:00:00','2026-11-08')]:
             with pytest.raises(ValueError): confirmed_window([],'RepoMind',lo,hi)
         for r in [row('2026-11-07'),dict(row('2026-11-07T00:00:00Z'),candidate_id='')]:
             with pytest.raises(ValueError): confirmed_window([r],'RepoMind','2026-11-07','2026-11-07')
     def test_independent_copies_and_order():
         a=row('2026-11-07T02:00:00Z');b=row('2026-11-07T01:00:00Z');a['extra']={'x':1}
         r=confirmed_window([a,b],'RepoMind','2026-11-07','2026-11-07');assert r==[a,b]
         r[0]['extra']['x']=2;assert a['extra']['x']==1
     '''),
    ("hold-source","source_lookup","source_lookup","codex.v4_acceptance_path",
     "Implement source_lookup(connection, project, source_id). Require nonblank string project and source_id, otherwise ValueError. Read existing SQLite tables only: nl_sources(project_id,source_id,source_json) and memory_review_candidates(project_id,status,candidate_json). Return the source_json decoded as a dict only if the exact project/source has a confirmed review whose candidate_json draft.source_id equals the source ID. Pending/rejected or another project must not authorize it. Missing tables or no authorized source returns None. Use parameterized SQL, do not create tables, write, commit, or roll back the caller transaction. Invalid stored source JSON or non-object JSON raises ValueError. SQLite JSON functions are available.",
     '''
     import json
     def source_lookup(connection,project,source_id):
         if any(not isinstance(v,str) or not v.strip() for v in (project,source_id)): raise ValueError('scope required')
         tables={r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
         if not {'nl_sources','memory_review_candidates'}<=tables: return None
         row=connection.execute("""SELECT s.source_json FROM nl_sources s WHERE s.project_id=? AND s.source_id=?
             AND EXISTS (SELECT 1 FROM memory_review_candidates r WHERE r.project_id=s.project_id
             AND r.status='confirmed' AND json_extract(r.candidate_json,'$.draft.source_id')=s.source_id)""",(project,source_id)).fetchone()
         if row is None: return None
         result=json.loads(row[0])
         if not isinstance(result,dict): raise ValueError('source must be object')
         return result
     ''',
     '''
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
     ''',
     '''
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
     '''),
]


def main():
    if SUITE.exists(): raise ValueError('preserve the existing frozen suite; do not overwrite')
    session_path=ROOT/'reports/v4.1/new-session.json'
    session=json.loads(session_path.read_text(encoding='utf-8'))
    snapshot={'mode':'reviewed-pilot-snapshot','project_id':'RepoMind','facts':session['recalled'],'experiences':[]}
    write(SUITE/'pilot-memory.json',json_text(snapshot))
    provenance={}
    for split in ('dev','holdout'):
        folder=SUITE/split
        prefix='dev-' if split=='dev' else 'hold-'
        selected=[row for row in TASKS if row[0].startswith(prefix)]
        for relative in ('__init__.py','domain/__init__.py','domain/models.py','memory/__init__.py','memory/resolver.py'):
            path='src/repomind/'+relative
            raw=subprocess.check_output(['git','show','v4.1.0:'+path],cwd=ROOT)
            write(folder/'repository'/path,raw.decode('utf-8'))
            provenance[path]=hashlib.sha256(raw).hexdigest()
        write(folder/'repository/pyproject.toml','[tool.pytest.ini_options]\npythonpath = ["src"]\n')
        write(folder/'repository/README.md','# RepoMind isolated maintenance tasks\n\nV4.1 core snapshot plus new maintenance helper contracts. Only the declared task source is writable.\n')
        tasks=[];actions=[]
        for tid,module,function,key,prompt,solution,public,hidden in selected:
            path='src/repomind/'+module+'.py'
            signature={'query_clock':'as_of, known_at=None, *, now','review_identity':'body, *, project',
                       'pack_facts':'facts, max_bytes','confirmed_window':'records, project, start, end',
                       'source_lookup':'connection, project, source_id'}.get(function,'text' if function=='explicit_key' else 'fact')
            stub='"""RepoMind maintenance helper. Contract is supplied in the task."""\n\ndef '+function+'('+signature+'):\n    raise NotImplementedError("implement the task contract")\n'
            write(folder/'repository'/path,stub)
            write(folder/f'public/{tid}/test_public.py',code(public))
            write(folder/f'judges/{tid}/test_acceptance.py',code(hidden))
            subject,field=key.split('.',1)
            tasks.append({'task_id':tid,'project_id':'RepoMind','category':module,
                          'prompt':f'RepoMind maintenance task. Relevant project evidence key: {key}. '+prompt+' Implement only '+path+'. Keep helpers generic; do not hardcode the current memory values.',
                          'as_of':'2026-11-07','memory_keys':[[subject,field]],'writable_paths':[path],
                          'public_test':f'public/{tid}/test_public.py','acceptance_test':f'judges/{tid}/test_acceptance.py',
                          'public_count':2,'acceptance_count':4})
            actions.append({'task_id':tid,'responses':[
                {'actions':[{'tool':'read_file','path':path},{'tool':'read_file','path':'tests/test_public.py'}]},
                {'actions':[{'tool':'write_file','path':path,'content':code(solution)}]},
                {'actions':[{'tool':'run_tests'},{'tool':'git_diff'}]},
                {'actions':[{'tool':'finish','summary':'Implemented the declared helper and verified public tests and diff.'}]},
            ]})
        write(folder/'tasks.jsonl',''.join(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n' for row in tasks))
        write(folder/'recorded-actions.jsonl',''.join(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n' for row in actions))
        files={p.relative_to(folder).as_posix():digest(p) for p in sorted(folder.rglob('*')) if p.is_file()}
        write(folder/'manifest.json',json_text({'stage_goal':'Freeze new V4.2 RepoMind '+split+' maintenance tasks','version':1,'split':split,'files':files}))
    write(SUITE/'provenance.json',json_text({'stage_goal':'Trace V4.2 task construction to the real pilot',
        'source_commit':subprocess.check_output(['git','rev-parse','v4.1.0^{commit}'],cwd=ROOT).decode().strip(),
        'unchanged_core_files':provenance,'task_construction':'New helper contracts derived from review, citation, context and date handling. Authored by the experiment implementer; not third-party blind production tasks.',
        'pilot_report':'reports/v4.1/new-session.json','pilot_sha256':digest(session_path),
        'disjoint_from_prior_suites':True,'dev_tasks':3,'holdout_tasks':4}))
    write(SUITE/'protocol.json',json_text({'stage_goal':'V4.2 freeze before selection and independent two-round validation',
        'version':3,'repetitions':2,'manifests':{split:digest(SUITE/split/'manifest.json') for split in ('dev','holdout')},
        'history_sha256':digest(session_path),'memory_sha256':digest(SUITE/'pilot-memory.json'),
        'provenance_sha256':digest(SUITE/'provenance.json'),'budget':AgentBudget().model_dump(),
        'max_model_requests':150,'max_completion_tokens':2048,
        'scoring':'v3_original_quality_and_same_gain_two_rounds_10_percent_tokens',
        'image':'sha256:bc6c2f2343c2855ee369fe9b20f5b834350eab234b96d14e48ec5e0038d0eb97'}))
    print('Frozen 3 development and 4 new holdout tasks; no model requests issued.')


if __name__=='__main__': main()
