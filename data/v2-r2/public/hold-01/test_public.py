import pytest
from parcelkit.discounts import discounted_minor

def test_common():
    assert discounted_minor(1000, 1000) == 900
def test_full():
    assert discounted_minor(123, 10000) == 0
