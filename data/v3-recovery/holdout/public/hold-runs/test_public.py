import pytest
from relaybox.collapse_runs import collapse_runs

def test_case_1():
    assert collapse_runs(["a", "a", "b"], 3) == [("a", 2), ("b", 1)]

def test_case_2():
    assert collapse_runs([], 1) == []
