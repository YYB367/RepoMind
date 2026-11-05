import pytest
from relaybox.collapse_runs import collapse_runs

def test_case_1():
    assert collapse_runs(["a"] * 7, 3) == [("a", 3), ("a", 3), ("a", 1)]

def test_case_2():
    assert collapse_runs(["", "", "A", "a"], 1) == [("", 1), ("", 1), ("A", 1), ("a", 1)]

def test_case_3():
    with pytest.raises(ValueError): collapse_runs([], True)

def test_case_4():
    with pytest.raises(ValueError): collapse_runs(["a", 1], 2)
