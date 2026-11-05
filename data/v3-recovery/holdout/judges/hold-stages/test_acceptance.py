import pytest
from relaybox.dependency_stages import dependency_stages

def test_case_1():
    assert dependency_stages({"c": ["b"], "b": ["a", "a"], "a": []}) == [("a",), ("b",), ("c",)]

def test_case_2():
    with pytest.raises(ValueError): dependency_stages({"a": ["unknown"]})

def test_case_3():
    with pytest.raises(ValueError): dependency_stages({"a": ["b"], "b": ["a"], "c": []})

def test_case_4():
    data = {"a": ["b"], "b": []}; dependency_stages(data); assert data == {"a": ["b"], "b": []}
