import pytest
from parcelkit.retry import retry_delay

def test_cap():
    assert retry_delay(5) == 30
    assert retry_delay(10) == 30
def test_before_cap():
    assert retry_delay(4) == 16
def test_large():
    assert retry_delay(1000000000) == 30
def test_invalid():
    for x in [True, -1, 1.1]:
        with pytest.raises(ValueError): retry_delay(x)
