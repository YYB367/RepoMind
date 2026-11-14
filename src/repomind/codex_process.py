"""Drain both pipes while emitting JSONL activity without starting another model."""
import json
import queue
import shlex
import subprocess
import threading
import time
from types import SimpleNamespace

from repomind.codex_activity import MAX_LINE, MAX_TRANSCRIPT


def stream_process(argv, *, input, cancel, on_event=None, on_tick=None, **kwargs):
    timeout = kwargs.pop('timeout', 1800)
    kwargs.pop('capture_output', None)
    messages = queue.Queue(maxsize=64)
    with subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs) as child:
        def read(name, pipe):
            try:
                while True:
                    value = pipe.readline(MAX_LINE + 1)
                    if not value:
                        break
                    messages.put((name, value))
            finally:
                messages.put((name, None))

        def write():
            try:
                child.stdin.write(input)
                child.stdin.close()
            except (BrokenPipeError, OSError):
                pass

        readers = [threading.Thread(target=read, args=(name, pipe), daemon=True)
                   for name, pipe in (('stdout', child.stdout), ('stderr', child.stderr))]
        for thread in readers:
            thread.start()
        writer = threading.Thread(target=write, daemon=True); writer.start()
        started = time.monotonic(); last_tick = started; ended = set()
        output = {'stdout': [], 'stderr': []}; size = 0; failure = None
        try:
            while len(ended) < 2 or child.poll() is None:
                if failure is None:
                    if cancel.is_set():
                        failure = '任务服务停止；未自动重试。'
                    elif time.monotonic() - started >= timeout:
                        failure = '任务超过运行时限；未自动重试。'
                    if failure and child.poll() is None:
                        child.terminate()
                if failure and child.poll() is None and time.monotonic() - last_tick > 5:
                    child.kill()
                try:
                    name, line = messages.get(timeout=.2)
                except queue.Empty:
                    line = ''
                if line is None:
                    ended.add(name)
                elif line:
                    length = len(line.encode('utf-8', errors='replace'))
                    size += length
                    if length > MAX_LINE or size > MAX_TRANSCRIPT:
                        failure = 'Codex 输出超过保存上限，任务已停止；已有失败证据保留。'
                        if child.poll() is None: child.terminate()
                    elif failure is None:
                        output[name].append(line)
                        if name == 'stdout' and on_event:
                            try: event = json.loads(line)
                            except (ValueError, TypeError): event = None
                            if isinstance(event, dict): on_event(event)
                if failure is None and on_tick and time.monotonic() - last_tick >= 2:
                    on_tick(); last_tick = time.monotonic()
        except BaseException:
            if child.poll() is None:
                child.terminate()
                try: child.wait(timeout=5)
                except subprocess.TimeoutExpired: child.kill(); child.wait(timeout=5)
            # Drain the bounded queue so reader threads can release their pipe locks.
            while any(t.is_alive() for t in readers):
                try: messages.get(timeout=.2)
                except queue.Empty: pass
            raise
        child.wait(timeout=5)
        for thread in readers: thread.join(1)
        writer.join(1)
        if on_event and (failure or child.returncode):
            on_event({'type': 'item.completed', 'item': {
                'id': 'repomind-process', 'type': 'command_execution',
                'command': shlex.join(map(str, argv)), 'exit_code': child.returncode,
                'status': 'failed', 'aggregated_output': failure or ''.join(output['stderr'])[-8000:]}})
        if failure:
            raise ValueError(failure)
        return SimpleNamespace(returncode=child.returncode, **{key: ''.join(value) for key, value in output.items()})
