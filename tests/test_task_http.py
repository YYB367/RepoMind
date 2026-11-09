from contextlib import contextmanager
import threading
import time

from test_workbench import request
from test_task_workbench import project
from repomind.codex_flow import capture
from repomind.web.server import WorkbenchServer
from repomind.web.tasks import TaskService


@contextmanager
def serving(db,root):
    with WorkbenchServer(db,0,roots={'RepoMind':root}) as server:
        thread=threading.Thread(target=server.serve_forever,kwargs={'poll_interval':.01},daemon=True);thread.start()
        try:yield server
        finally:server.shutdown();thread.join(3)


def test_task_http_preflight_start_preview_and_scope(project,monkeypatch):
    root,db=project
    monkeypatch.setattr(TaskService,'environment',lambda *_:{'ready':True,'checks':[]})
    def fake(root,database,project,prompt,**kwargs):
        (root/'decision.py').write_text("mode = 'reference'\n")
        message='```repomind-memory\n[{"path":"decision.py","quote":"reference","subject":"app","field":"mode","value":"reference","event_type":"declare","reason":"implemented in source"}]\n```'
        return {'session_id':'simulated','assistant_message':'Implemented.','capture':capture(root,database,project,message)}
    monkeypatch.setattr('repomind.web.tasks._run',fake)
    with serving(db,root) as server:
        assert request(server,'/tasks')[0]==200
        assert request(server,'/api/projects')[1]['task_projects']==['RepoMind']
        assert request(server,'/api/tasks/prepare',{'project':'RepoMind','prompt':'Do work','root':'C:/'} )[0]==400
        prepared=request(server,'/api/tasks/prepare',{'project':'RepoMind','prompt':'Improve source'})[1]
        tid=prepared['task_id'];url='/api/tasks/'+tid
        assert request(server,'/tasks?project=RepoMind&task='+tid)[0]==200
        assert request(server,'/review?project=RepoMind&candidate=review-'+'a'*64)[0]==200
        assert request(server,url+'/start',{'project':'RepoMind'},trusted=False)[0]==403
        assert request(server,url+'/start',{'project':'RepoMind'})[0]==202
        for _ in range(100):
            done=request(server,url+'?project=RepoMind')[1]
            if done['status'] not in {'queued','running'}:break
            time.sleep(.03)
        assert done['status']=='completed' and done['changes'][0]['diff']
        cid=done['candidates'][0]['candidate_id']
        p=request(server,'/api/candidates/'+cid+'/preview?project=RepoMind')[1]
        assert p['version_match'] and p['scope']=='task_snapshot' and p['task_id']==tid
        assert request(server,'/api/candidates/'+cid+'?project=Other')[0]==404
        assert request(server,'/api/tasks?project=Other')[1]['items']==[]


def test_duplicate_start_and_busy_task_are_not_executed_twice(project,monkeypatch):
    root,db=project;release=threading.Event();calls=[]
    monkeypatch.setattr(TaskService,'environment',lambda *_:{'ready':True,'checks':[]})
    def fake(*args,**kwargs):
        calls.append(1);release.wait(3)
        return {'session_id':'simulated','assistant_message':'No change.','capture':{'pending_ids':[],'created':0}}
    monkeypatch.setattr('repomind.web.tasks._run',fake)
    with serving(db,root) as server:
        a=request(server,'/api/tasks/prepare',{'project':'RepoMind','prompt':'A'})[1]
        b=request(server,'/api/tasks/prepare',{'project':'RepoMind','prompt':'B'})[1]
        url='/api/tasks/'+a['task_id']+'/start'
        try:
            assert request(server,url,{'project':'RepoMind'})[0]==202
            assert request(server,url,{'project':'RepoMind'})[0]==202
            assert request(server,'/api/tasks/'+b['task_id']+'/start',{'project':'RepoMind'})[0]==409
        finally:release.set()
        for _ in range(100):
            row=server.tasks.get('RepoMind',a['task_id'])
            if row['status']=='completed':break
            time.sleep(.02)
        assert len(calls)==1 and row['notice']
