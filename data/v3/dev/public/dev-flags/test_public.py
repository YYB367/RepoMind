import pytest
from signalbox.parse_flags import parse_flags

def test_case_1():
    assert parse_flags(" A=x ; b= ; a=Y ") == {"a": "Y", "b": ""}

def test_case_2():
    assert parse_flags("; ;") == {}
