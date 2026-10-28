"""Fixed Docker test commands; no host-Python fallback or model shell input."""
from collections import deque
import json
import os
from pathlib import Path
import re
import subprocess
import threading
import time
from uuid import uuid4

from repomind.agent.workspace import checked_path


def local_engine():
    return 'npipe:////./pipe/dockerDesktopLinuxEngine' if os.name=='nt' else 'unix:///var/run/docker.sock'


def docker_env():
    return {name:os.environ[name] for name in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP','USERPROFILE','APPDATA','LOCALAPPDATA') if name in os.environ}


def limited_process(args,*,timeout,max_bytes):
    """Drain a pipe into bounded memory; stop the client on time/output limit."""
    started=time.perf_counter()
    process=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,env=docker_env(),
                             creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    chunks=deque()
    count=0
    overflow=threading.Event()
    def reader():
        nonlocal count
        try:
            while block:=process.stdout.read(4096):
                available=max_bytes-count
                if available>0:
                    chunks.append(block[:available])
                    count+=len(block[:available])
                if len(block)>available:
                    overflow.set()
        except (ValueError,OSError):
            pass
    thread=threading.Thread(target=reader,daemon=True)
    thread.start()
    reason=None
    while process.poll() is None:
        if overflow.is_set():
            reason='output_limit'
            break
        if time.perf_counter()-started>timeout:
            reason='timeout'
            break
        time.sleep(.02)
    if reason:
        process.kill()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
    thread.join(timeout=2)
    process.stdout.close()
    if overflow.is_set():
        reason='output_limit'
    return {'exit_code':process.returncode,'stdout':b''.join(chunks).decode('utf-8',errors='replace'),
            'limit_reason':reason,'elapsed_seconds':time.perf_counter()-started}


class DockerSandbox:
    def __init__(self,image,config_dir,*,engine_host=None,timeout_seconds=25,max_output_bytes=65536):
        if not isinstance(image,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',image):
            raise ValueError('agent tests require an explicit local immutable Docker image ID')
        self.image=image
        self.config_dir=Path(config_dir).absolute()
        self.config_dir.mkdir(parents=True,exist_ok=True)
        self.engine_host=engine_host or local_engine()
        if self.engine_host not in {'npipe:////./pipe/dockerDesktopLinuxEngine','unix:///var/run/docker.sock'}:
            raise ValueError('only the local Linux engine is supported')
        if type(timeout_seconds) is not int or not 1<=timeout_seconds<=60:
            raise ValueError('sandbox timeout must be 1..60 seconds')
        if type(max_output_bytes) is not int or not 4096<=max_output_bytes<=262144:
            raise ValueError('sandbox output limit must be 4096..262144 bytes')
        self.timeout_seconds,self.max_output_bytes=timeout_seconds,max_output_bytes
        self._metadata=None

    def command(self,*args):
        return ['docker','--config',str(self.config_dir),'--host',self.engine_host,*args]

    def _read(self,*args):
        result=limited_process(self.command(*args),timeout=10,max_bytes=65536)
        if result['exit_code']!=0 or result['limit_reason']:
            raise ValueError('Docker Linux engine/image unavailable; no host-code fallback is permitted')
        return result['stdout'].strip()

    def probe(self):
        if self._read('info','--format','{{.OSType}}')!='linux':
            raise ValueError('agent execution requires the local Linux engine')
        row=json.loads(self._read('image','inspect',self.image))[0]
        if row['Id']!=self.image or row['Os']!='linux' or row['Config'].get('User')!='65532:65532':
            raise ValueError('unexpected test image identity/platform/user')
        self._metadata={'backend':'docker_linux','image_id':self.image,'engine_version':self._read('version','--format','{{.Server.Version}}'),
                        'network':'none','root_filesystem':'read-only','project_mount':'read-only',
                        'user':'65532:65532','capabilities':'ALL dropped','no_new_privileges':True,
                        'memory_mb':256,'cpus':1,'pids_limit':64,'timeout_seconds':self.timeout_seconds,
                        'max_output_bytes':self.max_output_bytes,'host_code_fallback':False,
                        'security_claim':'host capability isolation; not a hostile-code anti-cheating service or kernel-vulnerability guarantee'}
        return dict(self._metadata)

    def safe_metadata(self):
        if self._metadata is None:
            return self.probe()
        return dict(self._metadata)

    def run_args(self,repo,*,judge_dir=None,name,owner):
        repo=Path(repo).absolute()
        checked_path(repo,'tests/test_public.py')
        if ',' in str(repo) or (judge_dir and ',' in str(judge_dir)):
            raise ValueError('Docker bind source paths must not contain commas')
        args=self.command('run','--rm','--pull=never','--name',name,'--label','org.repomind.owner='+owner,
            '--network=none','--ipc=none','--user','65532:65532','--cap-drop=ALL',
            '--security-opt','no-new-privileges=true','--read-only','--cpus=1','--memory=256m',
            '--memory-swap=256m','--pids-limit=64','--ulimit','nofile=256:256',
            '--tmpfs','/tmp:rw,noexec,nosuid,nodev,size=32m,mode=1777',
            '--env','PYTEST_DISABLE_PLUGIN_AUTOLOAD=1',
            '--mount',f'type=bind,source={repo},target=/workspace,readonly',
            '--workdir','/workspace')
        target='/workspace/tests/test_public.py'
        if judge_dir is not None:
            judge_dir=Path(judge_dir).absolute()
            checked_path(judge_dir,'test_acceptance.py')
            args+=['--mount',f'type=bind,source={judge_dir},target=/judge,readonly']
            target='/judge/test_acceptance.py'
        return args+[self.image,'-I','-B','/opt/repomind-test-runner.py',target]

    def _cleanup(self,name,owner):
        # Only a generated name AND matching ownership label authorize removal.
        result=limited_process(self.command('inspect','--format','{{index .Config.Labels "org.repomind.owner"}}',name),timeout=5,max_bytes=4096)
        if result['exit_code']:
            check=limited_process(self.command('ps','-a','--filter','name=^/'+name+'$','--format','{{.Names}}'),timeout=5,max_bytes=4096)
            return check['exit_code']==0 and not check['stdout'].strip()
        if result['stdout'].strip()!=owner:
            return False
        removed=limited_process(self.command('rm','--force',name),timeout=5,max_bytes=4096)
        return removed['exit_code']==0

    def run_tests(self,repo,*,expected_count,judge_dir=None):
        if self._metadata is None:
            self.probe()
        owner=uuid4().hex
        name='repomind-v2-'+owner
        args=self.run_args(repo,judge_dir=judge_dir,name=name,owner=owner)
        result=limited_process(args,timeout=self.timeout_seconds,max_bytes=self.max_output_bytes)
        cleanup=self._cleanup(name,owner)
        report=None
        for line in result['stdout'].splitlines():
            if line.startswith('REPOMIND_RESULT '):
                try:
                    report=json.loads(line[len('REPOMIND_RESULT '):])
                except ValueError:
                    report=None
        valid=(isinstance(report,dict) and set(report)=={'exit_code','collected','passed','failed','skipped','errors'}
               and all(type(value) is int and value>=0 for value in report.values()))
        passed=(valid and report['collected']==expected_count and report['passed']==expected_count
                and report['failed']==report['skipped']==report['errors']==report['exit_code']==0
                and result['exit_code']==0 and not result['limit_reason'] and cleanup)
        infrastructure=(not cleanup or result['exit_code'] in {125,126,127})
        execution_error=result['limit_reason'] or ('invalid_guest_result' if not valid else None)
        return {**result,'passed':bool(passed),'test_report':report,'expected_count':expected_count,
                'infrastructure_error':infrastructure,'execution_error':execution_error,'cleanup_verified':cleanup,'container_name':name,
                'judge_visible_to_agent':False if judge_dir else None}


def prepare_image(project_root,config_dir,*,output_path):
    """Explicit trusted build. Image pulls/installations never occur in model tools."""
    root=Path(project_root).resolve()
    config=Path(config_dir).absolute()
    config.mkdir(parents=True,exist_ok=True)
    prefix=['docker','--config',str(config),'--host',local_engine()]
    result=limited_process(prefix+['build','--pull','--tag','repomind-agent:2.0.0',str(root/'docker/v2')],timeout=600,max_bytes=262144)
    if result['exit_code'] or result['limit_reason']:
        raise ValueError('trusted Docker image build failed; inspect the build output locally')
    inspected=limited_process(prefix+['image','inspect','repomind-agent:2.0.0'],timeout=10,max_bytes=65536)
    if inspected['exit_code']:
        raise ValueError('cannot inspect the built image')
    image=json.loads(inspected['stdout'])[0]['Id']
    sandbox=DockerSandbox(image,config)
    metadata=sandbox.probe()
    path=Path(output_path)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({'stage_goal':'V2 isolated code test image','image':image,'sandbox':metadata},indent=2)+'\n',encoding='utf-8',newline='\n')
    return {'image':image,'config':str(path.resolve()),'sandbox':metadata}
