import pytest
from relaybox.batch_key import batch_key

def test_case_1():
    assert batch_key("ß:MAIN:001") == ("ss", "main", "001")

def test_case_2():
    with pytest.raises(ValueError): batch_key("r:two words:k")

def test_case_3():
    with pytest.raises(ValueError): batch_key("x:y: ")

def test_case_4():
    with pytest.raises(ValueError): batch_key(None)
