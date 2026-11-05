import pytest
from relaybox.batch_key import batch_key

def test_case_1():
    assert batch_key(" EU : App : X0 ") == ("eu", "app", "X0")

def test_case_2():
    with pytest.raises(ValueError): batch_key("x:y")
