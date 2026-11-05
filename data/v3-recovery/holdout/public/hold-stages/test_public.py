import pytest
from relaybox.dependency_stages import dependency_stages

def test_case_1():
    assert dependency_stages({"z": ["a"], "b": [], "a": []}) == [("a", "b"), ("z",)]

def test_case_2():
    assert dependency_stages({}) == []
