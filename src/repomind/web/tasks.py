"""Single local task runner, durable receipts, and project-scoped evidence."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import threading
from types import SimpleNamespace
from uuid import uuid4

from repomind.adapters.sqlite import SQLiteMemoryStore
from repomind.codex_cli import _run
from repomind.codex_flow import recall
from repomind.memory.review import ReviewQueue
from repomind.web.evidence import changes, git, preview, snapshot


def now():
    return datetime.now(timezone.utc).isoformat()


class TaskService:
    def __init__(self,database,roots,run=None):
        self.database=database
        self.roots={name:Path(root).resolve() for name,root in roots.items()}
        self.run=run or _run
        self.mutex=threading.RLock();self.cancel=threading.Event();self.thread=None
        self.database.parent.mkdir(parents=True,exist_ok=True)
        self.lease=open(str(database)+'.tasks-lock','a+b')
        self.lease.seek(0);self.lease.write(b'0');self.lease.flush();self.lease.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.lease.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.lease.close()
            raise ValueError('同一记忆库已有任务服务，请使用已有工作台。') from None
        with SQLiteMemoryStore(database) as store:
            store.connection.execute('CREATE TABLE IF NOT EXISTS web_tasks (task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, status TEXT NOT NULL, receipt TEXT NOT NULL)')
            store.connection.execute('CREATE TABLE IF NOT EXISTS web_task_candidates (project_id TEXT NOT NULL, candidate_id TEXT NOT NULL, task_id TEXT NOT NULL, PRIMARY KEY(project_id,candidate_id))')
            for record, in store.connection.execute("SELECT receipt FROM web_tasks WHERE status IN ('queued','running')").fetchall():
                row=json.loads(record);row.update(status='interrupted',ended_at=now(),error='上次任务服务中断；未自动重跑。请核对原 Codex 进程及文件后再启动新任务。')
                row.pop('_before',None);self._save(store,row)

    def close(self):
        self.cancel.set()
        if self.thread:self.thread.join(12)
        self.lease.close()

    def root(self,project):
        if project not in self.roots:raise ValueError('项目未登记任务目录，请在服务启动配置中登记。')
        return self.roots[project]

    @staticmethod
    def _save(store,row):
        store.connection.execute('INSERT OR REPLACE INTO web_tasks VALUES (?,?,?,?)',
            (row['task_id'],row['project'],row['status'],json.dumps(row,ensure_ascii=False)))

    def get(self,project,tid,*,internal=False):
        with SQLiteMemoryStore(self.database,read_only=True) as store:
            record=store.connection.execute('SELECT receipt FROM web_tasks WHERE project_id=? AND task_id=?',(project,tid)).fetchone()
        if record is None:raise ValueError('当前项目没有这项任务。')
        row=json.loads(record[0])
        if not internal and row.get('candidates'):
            with SQLiteMemoryStore(self.database,read_only=True) as store:
                queue=ReviewQueue(store,initialize=False)
                row['candidates']=[queue.show(project,c['candidate_id']).model_dump(mode='json') for c in row['candidates']]
        return row if internal else {k:v for k,v in row.items() if not k.startswith('_')}

    def listing(self,project):
        with SQLiteMemoryStore(self.database,read_only=True) as store:
            rows=[json.loads(row[0]) for row in store.connection.execute('SELECT receipt FROM web_tasks WHERE project_id=? ORDER BY rowid DESC LIMIT 50',(project,))]
        return [{k:row.get(k) for k in ('task_id','project','prompt','status','created_at','ended_at')} for row in rows]

    def environment(self,project):
        root=self.root(project);checks=[]
        def check(name,fn):
            try:
                ok,detail=fn()
            except (OSError,ValueError,subprocess.SubprocessError):ok,detail=False,'检查失败，请在同一终端核对运行环境。'
            checks.append({'name':name,'ok':ok,'detail':detail})
        check('项目目录',lambda:(root.is_dir(),str(root)))
        check('Git',lambda:(Path(git(root,'rev-parse','--show-toplevel').decode().strip()).resolve()==root,'已核对项目仓库根目录'))
        check('Python',lambda:(True,sys.executable))
        codex=shutil.which('codex')
        check('Codex CLI',lambda:(bool(codex),subprocess.run(['codex','--version'],capture_output=True,text=True,timeout=10).stdout.strip()))
        check('Codex 登录',lambda:(subprocess.run(['codex','login','status'],capture_output=True,timeout=15).returncode==0,'读取当前 Codex 登录，不显示凭据'))
        def sandbox():
            # A bounded file round trip inside the registered project, no model request.
            script="import pathlib,tempfile; p=pathlib.Path('work'); p.mkdir(exist_ok=True); f=tempfile.TemporaryFile(dir=p); f.write(b'probe'); f.seek(0); assert f.read()==b'probe'; f.close()"
            child=subprocess.run(['codex','sandbox','-C',str(root),'--permission-profile',':workspace','--',sys.executable,'-c',script],
                                 cwd=root,capture_output=True,timeout=45)
            return child.returncode==0,'workspace 沙箱读写探测通过' if child.returncode==0 else 'workspace 沙箱不可用；请在终端修复后重新预查'
        if codex:check('读写沙箱',sandbox)
        return {'ready':len(checks)==6 and all(c['ok'] for c in checks),'checks':checks,'root':str(root),'sandbox':'workspace-write'}

    def prepare(self,project,prompt):
        root=self.root(project)
        if not prompt.strip() or len(prompt)>8000:raise ValueError('任务内容须为 1–8000 个字符。')
        environment=self.environment(project)
        row={'task_id':'task-'+uuid4().hex,'project':project,'prompt':prompt.strip(),'status':'prepared',
             '_root':str(root),
             'created_at':now(),'environment':environment,'recalled':recall(self.database,project,prompt),
             'changes':[],'candidates':[],'result':None,'error':None}
        with SQLiteMemoryStore(self.database) as store:self._save(store,row)
        return self.get(project,row['task_id'])

    def start(self,project,tid):
        with self.mutex,SQLiteMemoryStore(self.database) as store,store.write_transaction():
            row=self.get(project,tid,internal=True)
            if row['status'] in {'queued','running'}:return self.get(project,tid)
            if row['status']!='prepared' or not row['environment']['ready']:raise ValueError('任务尚未通过环境预查，或已启动过。')
            if row.get('_root')!=str(self.root(project)):raise ValueError('项目目录已变化，请重新预查。')
            if store.connection.execute("SELECT 1 FROM web_tasks WHERE status IN ('queued','running')").fetchone():
                raise ValueError('已有开发任务运行中，请等待其结束。')
            if recall(self.database,project,row['prompt'])!=row['recalled']:
                raise ValueError('已确认记忆已变化，请重新预查并核对。')
            row.update(status='queued');self._save(store,row)
        self.thread=threading.Thread(target=self._work,args=(project,tid),daemon=True)
        self.thread.start()
        return self.get(project,tid)

    def execute(self,argv,*,input,**kwargs):
        kwargs.pop('timeout',None)
        kwargs.pop('capture_output',None)
        with subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,**kwargs) as child:
            supplied=input;elapsed=0
            while True:
                try:
                    out,err=child.communicate(input=supplied,timeout=.5)
                    return SimpleNamespace(returncode=child.returncode,stdout=out,stderr=err)
                except subprocess.TimeoutExpired:
                    supplied=None;elapsed+=.5
                    if self.cancel.is_set() or elapsed>=1800:
                        child.terminate()
                        try:child.communicate(timeout=5)
                        except subprocess.TimeoutExpired:child.kill();child.communicate()
                        raise ValueError('任务服务停止或超过 30 分钟；未自动重试。')

    def _work(self,project,tid):
        row=self.get(project,tid,internal=True);root=self.root(project)
        try:
            before=snapshot(root);row.update(status='running',started_at=now(),_before=before)
            with SQLiteMemoryStore(self.database) as store:self._save(store,row)
            guidance=(row['prompt']+'\n\n运行环境说明：本项目测试解释器为 '+sys.executable+
                      '。只完成这项开发任务，保留既有未提交改动与冻结数据；不要提交 Git，不要编辑记忆数据库或执行审核命令。'+
                      '候选必须来自实际文件产出；不要因为有任务就编造事实。')
            row['result']=self.run(root,self.database,project,guidance,workspace_write=True,
                                   facts_override=row['recalled'],runner=self.execute)
            row['status']='completed'
            row['changes']=changes(before,snapshot(root))
            if not row['changes']:
                row['notice']='会话已结束，本次未检测到允许范围内的文件改动。请核对助手结果。'
            ids=row['result']['capture']['pending_ids']
            with SQLiteMemoryStore(self.database) as store:
                queue=ReviewQueue(store)
                for cid in ids:
                    candidate=queue.show(project,cid)
                    row['candidates'].append(candidate.model_dump(mode='json'))
                    store.connection.execute('INSERT OR IGNORE INTO web_task_candidates VALUES (?,?,?)',(project,cid,tid))
        except Exception as error:
            row.update(status='cancelled' if self.cancel.is_set() else 'failed',error=str(error) if isinstance(error,ValueError) else '任务执行失败，请检查同一终端的 Codex 环境。')
            try:row['changes']=changes(row.get('_before',{}),snapshot(root))
            except (OSError,ValueError,subprocess.SubprocessError):pass
        finally:
            row.pop('_before',None);row['ended_at']=now()
            with SQLiteMemoryStore(self.database) as store:self._save(store,row)

    def candidate_preview(self,project,candidate):
        with SQLiteMemoryStore(self.database,read_only=True) as store:
            record=store.connection.execute('SELECT task_id FROM web_task_candidates WHERE project_id=? AND candidate_id=?',(project,candidate.candidate_id)).fetchone()
        task=self.get(project,record[0]) if record else None
        result=preview(self.roots.get(project),candidate,task)
        return result | {'task_id':task['task_id'] if task else None}
