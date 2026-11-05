import pytest
from relaybox.transfer_stock import transfer_stock

def test_case_1():
    assert transfer_stock({"a": 3, "b": 0, "c": 0}, [("a", "b", 2), ("b", "c", 2)]) == {"a": 1, "b": 0, "c": 2}

def test_case_2():
    with pytest.raises(ValueError): transfer_stock({"a": True}, [])

def test_case_3():
    with pytest.raises(ValueError): transfer_stock({"a": 2, "b": 0}, [("a", "b", True)])

def test_case_4():
    original = {"a": 2, "b": 0}; assert transfer_stock(original, [("a", "b", 1)]) == {"a": 1, "b": 1}; assert original == {"a": 2, "b": 0}
