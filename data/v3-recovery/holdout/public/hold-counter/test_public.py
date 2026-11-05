import pytest
from relaybox.daily_counters import daily_counters

def test_case_1():
    assert daily_counters([("mon", "x", 3), ("mon", "x", -2)]) == {"mon": {"x": 1}}

def test_case_2():
    assert daily_counters([]) == {}
