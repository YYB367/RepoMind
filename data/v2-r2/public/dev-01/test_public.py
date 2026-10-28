import pytest
from parcelkit.money import money_minor

def test_common():
    assert money_minor('12.34') == 1234
def test_zero():
    assert money_minor(0) == 0
