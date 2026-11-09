"""Bounded, text-only project evidence and task-relative file snapshots."""
import difflib
import hashlib
from pathlib import Path
import re
import subprocess

from repomind.agent.models import relative_path
from repomind.agent.workspace import checked_path
from repomind.platform.tracing import clean_payload

MAX_FILE = 256 * 1024
MAX_SNAPSHOT = 4 * 1024 * 1024
SUFFIXES = {'.md', '.py', '.json', '.txt'}


def git(root, *args):
    child = subprocess.run(['git', '-c', 'safe.directory='+str(root), '--no-replace-objects',
                            '-C', str(root), *args], capture_output=True, timeout=15)
    if child.returncode:
        raise ValueError('无法读取项目 Git 记录。')
    return child.stdout


def allowed(path,*,text=True):
    name = relative_path(path)
    parts = Path(name).parts
    if ((text and Path(name).suffix.lower() not in SUFFIXES) or any(p.startswith('.') for p in parts)
            or parts[0] in {'work', 'dist', 'build', 'node_modules'}
            or any(re.search(r'(?i)secret|credential|password|token|auth', p) for p in parts)):
        raise ValueError('路径不在允许预览的文本范围内。')
    return name


def read_text(root, relative):
    path = checked_path(root, allowed(relative))
    with path.open('rb') as stream:
        raw = stream.read(MAX_FILE+1)
    if len(raw)>MAX_FILE:
        raise ValueError('文件超过 256 KiB 预览上限。')
    text = raw.decode('utf-8-sig')
    if '\0' in text or clean_payload(text)!=text:
        raise ValueError('文件不是可安全预览的普通文本。')
    return {'text':text, 'sha256':hashlib.sha256(raw).hexdigest(), 'bytes':len(raw)}


def snapshot(root):
    paths = sorted(set(git(root, 'ls-files', '-co', '--exclude-standard', '-z').decode('utf-8').split('\0')),
                   key=lambda p: (not p.startswith(('src/', 'tests/', 'docs/')), p))
    result = {}; used=0
    for relative in filter(None, paths[:5000]):
        try:
            record=read_text(root, relative)
            if used+record['bytes']>MAX_SNAPSHOT:
                record.pop('text')
            else:
                used+=record['bytes']
            result[relative]=record
        except (OSError,ValueError,UnicodeError):
            try:
                path=checked_path(root,allowed(relative,text=False));info=path.stat()
                with path.open('rb') as stream:raw=stream.read(MAX_FILE+1)
                fingerprint=hashlib.sha256(raw).hexdigest() if len(raw)<=MAX_FILE else None
                result[relative]={'sha256':fingerprint,'bytes':info.st_size,'mtime_ns':info.st_mtime_ns,
                                  'unavailable':'文件类型未支持、过大、非 UTF-8 或不适合文本预览。'}
            except (OSError,ValueError):pass
    return result


def changes(before, after):
    result=[]
    for path in sorted(before.keys() | after.keys()):
        a,b=before.get(path),after.get(path)
        if (a and b and a['sha256']==b['sha256'] and (a['sha256'] is not None
                or (a.get('bytes'),a.get('mtime_ns'))==(b.get('bytes'),b.get('mtime_ns')))):
            continue
        old=a.get('text') if a else ''
        new=b.get('text') if b else ''
        diff=None
        if old is not None and new is not None:
            diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),
                         fromfile='before/'+path,tofile='after/'+path))[:100000]
        result.append({'path':path,'kind':'added' if a is None else 'deleted' if b is None else 'modified',
                       'before':a,'after':b,'diff':diff,'diff_limited':bool(diff and len(diff)>=100000)})
    return result


def preview(root, candidate, task=None):
    artifact=candidate.artifact
    result={'path':artifact.path,'commit':artifact.commit,'expected_sha256':artifact.sha256,
            'quote':candidate.quote,'text':candidate.quote,'scope':'quote','version_match':False,
            'changed':False,'warning':None,'changes':task.get('changes',[]) if task else []}
    if root is None:
        return result | {'warning':'项目尚未登记目录，仅显示已保存引文。'}
    try:
        path=Path(artifact.path)
        relative=path.relative_to(root).as_posix() if path.is_absolute() else path.as_posix()
        allowed(relative)
        # Check present path components even for historical blobs; never follow links.
        checked_path(root,relative,must_exist=False)
        current=None
        try:
            current=read_text(root,relative)
        except (OSError,ValueError,UnicodeError):
            pass
        result['changed']=current is None or current['sha256']!=artifact.sha256
        if artifact.kind=='git':
            if not re.fullmatch('[0-9a-f]{40}|[0-9a-f]{64}',artifact.commit or ''):
                raise ValueError('提交标识无效。')
            blob=artifact.commit+':'+relative
            if int(git(root,'cat-file','-s',blob))>MAX_FILE:
                raise ValueError('提交中的文件超过 256 KiB 预览上限。')
            raw=git(root,'cat-file','blob',blob)
            record={'text':raw.decode('utf-8-sig'),'sha256':hashlib.sha256(raw).hexdigest()}
            scope='git'
        else:
            record=None;scope='file'
            if task:
                for change in task.get('changes',[]):
                    saved=change.get('after')
                    if change['path']==relative and saved and saved['sha256']==artifact.sha256 and 'text' in saved:
                        record=saved;scope='task_snapshot';break
            if record is None and current and current['sha256']==artifact.sha256:
                record=current
            if record is None:
                raise ValueError('原文件已改变、缺失或无法完整读取；仅显示审核时保存的引文。')
        if (record['sha256']!=artifact.sha256 or candidate.quote not in record['text']
                or '\0' in record['text'] or clean_payload(record['text'])!=record['text']):
            raise ValueError('来源摘要或引文与版本不匹配，仅显示已保存引文。')
        result.update(text=record['text'],scope=scope,version_match=True,
                      warning='当前工作区文件与候选版本不同；下方展示候选绑定的历史版本。' if result['changed'] else None)
    except (OSError,ValueError,UnicodeError) as error:
        result['warning']=(str(error) if isinstance(error,ValueError) and str(error).startswith(('原文件','来源摘要','提交中的文件')) else
            '来源不可完整预览：路径、版本或文件大小不符合要求。仅显示已保存引文，候选和编辑内容保留。')
    return result
