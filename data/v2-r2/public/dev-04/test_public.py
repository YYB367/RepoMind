import pytest
from parcelkit.retry import retry_delay

def test_first():
    assert retry_delay(0) == 1
def test_second():
    assert retry_delay(1) == 2
