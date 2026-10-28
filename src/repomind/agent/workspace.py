"""Owned task copies with an explicit file allowlist; never a user checkout."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
from repomind.agent.models import relative_path


class ToolDenied(ValueError):
    pass


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def checked_path(root,relative,*,must_exist=True):
    try:
        relative_path(relative)
        root=Path(root).absolute()
        for component in [root,*root.parents]:
            info=component.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400:
                raise ValueError('linked root')
        cursor=root
        for piece in relative.split('/'):
            cursor=cursor/piece
            if cursor.exists() or cursor.is_symlink():
                info=cursor.lstat()
                if stat.S_ISLNK(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400 or (cursor.is_file() and info.st_nlink>1):
                    raise ValueError('linked file')
        if not cursor.resolve().is_relative_to(root.resolve()) or (must_exist and not cursor.is_file()):
            raise ValueError('outside or missing file')
        return cursor
    except (ValueError,OSError):
        raise ToolDenied('path is outside the permitted task files or is linked/missing') from None


def git_env():
    names=('PATH','SYSTEMROOT','WINDIR','TEMP','TMP')
    result={key:os.environ[key] for key in names if key in os.environ}
    result.update(GIT_CONFIG_NOSYSTEM='1',GIT_CONFIG_GLOBAL=os.devnull,GIT_TERMINAL_PROMPT='0')
    return result


class TaskWorkspace:
    def __init__(self,root,task,benchmark_root):
        self.root=Path(root).absolute()
        self.task=task
        self.benchmark_root=Path(benchmark_root).resolve()
        if self.root.exists():
            raise ValueError('task workspace must be fresh; previous evidence is retained')
        self.root.mkdir(parents=True)
        self.allowed=[]
        source=self.benchmark_root/'repository'
        for path in sorted(source.rglob('*')):
            if path.is_file():
                relative=path.relative_to(source).as_posix()
                checked=checked_path(source,relative)
                target=self.root/relative
                target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes(checked.read_bytes())
                self.allowed.append(relative)
        public=checked_path(self.benchmark_root,task.public_test)
        target=self.root/'tests/test_public.py'
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(public.read_bytes())
        self.allowed.append('tests/test_public.py')
        if not set(task.writable_paths)<=set(self.allowed):
            raise ValueError('declared source does not exist in the sample repository')
        self._protected={p:digest(self.root/p) for p in self.allowed if p not in task.writable_paths}
        self._initial={p:digest(self.root/p) for p in self.allowed}
        self._git(['init','--quiet'])
        self._git(['add','--',*self.allowed])
        self._git(['-c','user.name=RepoMind Benchmark','-c','user.email=benchmark@invalid.local',
                   '-c','core.hooksPath='+os.devnull,'commit','--quiet','-m','Frozen sample task input'])
        self.protected_integrity()

    def _git(self,args):
        result=subprocess.run(['git','-c','core.fsmonitor=false',*args],cwd=self.root,env=git_env(),
                              capture_output=True,timeout=10)
        if result.returncode:
            raise ValueError('trusted sample Git operation failed')
        if len(result.stdout)>262144:
            raise ValueError('sample Git output exceeds limit')
        return result.stdout.decode('utf-8',errors='replace')

    def protected_integrity(self):
        for relative,expected in self._protected.items():
            if digest(checked_path(self.root,relative))!=expected:
                raise ToolDenied('protected sample file changed')
        for relative in self.task.writable_paths:
            checked_path(self.root,relative)
        return True

    def list_files(self):
        self.protected_integrity()
        return {'files':sorted(self.allowed),'writable_paths':self.task.writable_paths}

    def read_file(self,path,start_line=1,max_lines=120):
        self.protected_integrity()
        if path not in self.allowed:
            raise ToolDenied('file is not in the task read allowlist')
        target=checked_path(self.root,path)
        if target.stat().st_size>65536:
            raise ToolDenied('read exceeds file size limit')
        lines=target.read_text(encoding='utf-8').splitlines()
        return {'path':path,'start_line':start_line,'total_lines':len(lines),
                'content':'\n'.join(lines[start_line-1:start_line-1+max_lines])}

    def write_file(self,path,content):
        self.protected_integrity()
        if path not in self.task.writable_paths or len(content.encode('utf-8'))>65536:
            raise ToolDenied('write is not in the declared source scope or exceeds the byte limit')
        target=checked_path(self.root,path)
        if sum((self.root/p).stat().st_size for p in self.allowed)+len(content.encode('utf-8'))>1_000_000:
            raise ToolDenied('task file quota exceeded')
        target.write_text(content,encoding='utf-8',newline='\n')
        self.protected_integrity()
        return {'path':path,'bytes':target.stat().st_size,'sha256':digest(target)}

    def git_diff(self):
        self.protected_integrity()
        return {'diff':self._git(['--no-pager','diff','--no-ext-diff','--no-textconv','HEAD','--',*self.task.writable_paths])}

    def changed_files(self):
        return [p for p in self.task.writable_paths if digest(checked_path(self.root,p))!=self._initial[p]]
