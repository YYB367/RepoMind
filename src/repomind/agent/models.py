"""Explicit tasks and validated, finite-capability tool actions."""
from datetime import datetime
import re
from typing import Annotated, Literal, Union
from pydantic import Field, StringConstraints, field_validator, model_validator
from repomind.domain.models import Contract, Text, parse_timestamp


def relative_path(value: str) -> str:
    if not isinstance(value, str) or len(value)>240 or not value or '\\' in value or ':' in value:
        raise ValueError('expected a bounded POSIX relative path')
    parts=value.split('/')
    if any(p in {'','.','..'} or not re.fullmatch(r'[A-Za-z0-9_.-]+',p) or p.rstrip('. ')!=p
           or re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\..*)?',p) for p in parts):
        raise ValueError('unsafe relative path')
    return value


class AgentTask(Contract):
    task_id: Text
    project_id: Text
    category: Text
    prompt: Text
    as_of: datetime
    known_at: datetime|None=None
    memory_keys: list[tuple[Text,Text]]
    writable_paths: Annotated[list[Text],Field(min_length=1,max_length=8)]
    public_test: Text
    acceptance_test: Text
    public_count: Annotated[int,Field(ge=1,le=100)]
    acceptance_count: Annotated[int,Field(ge=1,le=100)]

    @field_validator('as_of','known_at',mode='before')
    @classmethod
    def times(cls,value):
        return None if value is None else parse_timestamp(value,allow_date=True)

    @model_validator(mode='after')
    def paths(self):
        for path in [*self.writable_paths,self.public_test,self.acceptance_test]:
            relative_path(path)
        if any(not p.startswith('src/') or not p.endswith('.py') for p in self.writable_paths):
            raise ValueError('only declared Python source files may be writable')
        return self


class ReadFile(Contract):
    tool: Literal['read_file']
    path: Text
    start_line: Annotated[int,Field(strict=True,ge=1)]=1
    max_lines: Annotated[int,Field(strict=True,ge=1,le=200)]=120


class WriteFile(Contract):
    tool: Literal['write_file']
    path: Text
    content: Annotated[str,StringConstraints(strict=True,max_length=65536)]


class ListFiles(Contract):
    tool: Literal['list_files']


class RunTests(Contract):
    tool: Literal['run_tests']


class GitDiff(Contract):
    tool: Literal['git_diff']


class Finish(Contract):
    tool: Literal['finish']
    summary: Annotated[str,StringConstraints(strict=True,strip_whitespace=True,min_length=1,max_length=1200)]


Action=Annotated[Union[ReadFile,WriteFile,ListFiles,RunTests,GitDiff,Finish],Field(discriminator='tool')]


class ActionBatch(Contract):
    actions: Annotated[list[Action],Field(min_length=1,max_length=4)]

    @model_validator(mode='after')
    def finish_alone(self):
        if any(a.tool=='finish' for a in self.actions) and len(self.actions)!=1:
            raise ValueError('finish must be the only action in its batch')
        return self


class AgentBudget(Contract):
    max_turns: Annotated[int,Field(strict=True,ge=1,le=12)]=6
    max_test_runs: Annotated[int,Field(strict=True,ge=1,le=5)]=3
    max_actions: Annotated[int,Field(strict=True,ge=1,le=48)]=20
    max_context_chars: Annotated[int,Field(strict=True,ge=2000,le=100000)]=24000
