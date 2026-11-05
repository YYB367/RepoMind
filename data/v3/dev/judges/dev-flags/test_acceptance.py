import pytest
from signalbox.parse_flags import parse_flags

def test_case_1():
    assert parse_flags("a=x=y") == {"a": "x=y"}

def test_case_2():
    with pytest.raises(ValueError): parse_flags("ok=1;bad")

def test_case_3():
    with pytest.raises(ValueError): parse_flags(" =value")

def test_case_4():
    with pytest.raises(ValueError): parse_flags(None)
