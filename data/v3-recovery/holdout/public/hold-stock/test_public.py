import pytest
from relaybox.transfer_stock import transfer_stock

def test_case_1():
    assert transfer_stock({"a": 3, "b": 2}, [("a", "b", 2)]) == {"a": 1, "b": 4}

def test_case_2():
    with pytest.raises(ValueError): transfer_stock({"a": 1, "b": 0}, [("a", "b", 2)])
