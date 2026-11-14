"""Bounded, sanitized execution evidence; never store reasoning or credentials."""
from datetime import datetime, timezone
import hashlib
import os
import re

from repomind.platform.tracing import clean_payload

MAX_LINE = 1024 * 1024
MAX_TRANSCRIPT = 16 * 1024 * 1024
MAX_EVENTS = 2000


def stamp():
    return datetime.now(timezone.utc).isoformat()


def safe_text(value, limit=8000):
    text = str(value or '')
    for name, secret in os.environ.items():
        if len(secret) >= 4 and re.search(r'key|token|secret|password|credential', name, re.I):
            text = text.replace(secret, '[REDACTED]')
    text = clean_payload(text)
    text = re.sub(r'(?im)\b(Authorization|Proxy-Authorization|Cookie|Set-Cookie)\s*:[^\r\n]*', r'\1: [REDACTED]', text)
    # Shell/JSON assignments, flags, URL query credentials and authenticated URLs.
    text = re.sub(r'''(?ix)((?:[\w.-]*(?:api[_-]?key|token|secret|password|authorization|cookie)[\w.-]*)["']?\s*(?:=|:|\s)\s*)("[^"]*"|'[^']*'|[^\s;&]+)''', r'\1[REDACTED]', text)
    text = re.sub(r'(https?://)[^\s/@]+:[^\s/@]+@', r'\1[REDACTED]@', text)
    text = re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', text)
    text = ''.join(c for c in text if c in '\n\t' or ord(c) >= 32)
    return text[:limit] + ('\n[已截断]' if len(text) > limit else '')


class ActivityLog:
    def __init__(self, data=None):
        self.data = data or {'source': 'codex_jsonl', 'events': [], 'omitted_events': 0}

    def observe(self, event):
        kind = event.get('type', '')
        if not isinstance(kind, str):
            return
        item = event.get('item') or {}
        if not isinstance(item, dict):
            return
        when = stamp()
        summary = {'thread.started': '独立会话已启动', 'turn.started': '助手正在处理任务',
                   'turn.completed': '助手会话已结束', 'turn.failed': '助手会话失败',
                   'error': '收到执行错误'}.get(kind)
        record = None
        if item.get('type') == 'command_execution' and kind in {'item.started', 'item.updated', 'item.completed'}:
            command = str(item.get('command') or '')
            code = item.get('exit_code')
            code = code if type(code) is int else None
            summary = ('命令执行结束' if kind == 'item.completed' else '正在执行命令') + '：' + safe_text(command, 240)
            if kind != 'item.updated':
                output = safe_text(item.get('aggregated_output'), 8000)
                record = {'at': when, 'event': kind, 'item_id': safe_text(item.get('id'), 120),
                          'command': safe_text(command), 'signature': hashlib.sha256(command.strip().encode()).hexdigest(),
                          'exit_code': code, 'status': safe_text(item.get('status'), 60),
                          'output': output, 'reason': output[-2000:] if code not in (None, 0) or item.get('status') == 'failed' else None}
        elif kind == 'item.completed' and item.get('type') == 'agent_message':
            summary = '助手已输出结果'
        elif kind == 'item.started' and item.get('type') != 'reasoning':
            summary = '助手正在操作：' + safe_text(item.get('type'), 80)
        if kind in {'error', 'turn.failed'}:
            error = event.get('error') or {}
            detail = event.get('message') or (error.get('message') if isinstance(error, dict) else error)
            summary += '：' + safe_text(detail, 1000)
        if summary:
            self.data.update(last_activity_at=when, summary=summary)
        if record:
            if len(self.data['events']) < MAX_EVENTS:
                self.data['events'].append(record)
            else:
                self.data['omitted_events'] += 1

    def view(self):
        return activity_view(self.data)


def activity_view(data):
    """Original event entries stay unchanged; retry links are derived separately."""
    latest = {}
    first_seen = {}; last_seen = {}
    for position, event in enumerate(data.get('events', [])):
        first_seen.setdefault(event['item_id'], position)
        last_seen[event['item_id']] = position
        latest[event['item_id']] = event
    commands = list(latest.values())
    failures = []
    for index, command in enumerate(commands):
        if command['exit_code'] in (None, 0) and command.get('status') != 'failed':
            continue
        later = [c for c in commands if c['signature'] == command['signature']
                 and first_seen[c['item_id']] > last_seen[command['item_id']]]
        outcome = ('succeeded' if later[-1]['exit_code'] == 0 else
                   'running' if later[-1]['exit_code'] is None and later[-1].get('status') != 'failed' else 'failed') if later else 'unknown'
        failures.append(dict(command, retry_outcome=outcome, retry_item_id=later[-1]['item_id'] if later else None))
    return dict(data, commands=commands, failures=failures)


def legacy_activity(row):
    failures = [{'exit_code': e.get('exit_code'), 'command': '旧版未记录命令', 'reason': '旧版未记录原因',
                 'retry_outcome': 'unknown'} for e in (row.get('result') or {}).get('tool_errors', [])]
    return {'source': 'legacy', 'events': [], 'commands': [], 'failures': failures,
            'last_activity_at': row.get('ended_at'), 'summary': '旧任务未保存活动流；无法还原命令和重试。'}
