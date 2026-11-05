import pytest
from relaybox.daily_counters import daily_counters

def test_case_1():
    assert daily_counters([("mon", "x", 2), ("mon", "x", -2), ("fri", "x", -4)]) == {"mon": {"x": 0}, "fri": {"x": -4}}

def test_case_2():
    assert daily_counters([("a", "X", 1), ("a", "x", 2)]) == {"a": {"X": 1, "x": 2}}

def test_case_3():
    with pytest.raises(ValueError): daily_counters([("mon", "x", True)])

def test_case_4():
    with pytest.raises(ValueError): daily_counters([("mon", "", 1)])
