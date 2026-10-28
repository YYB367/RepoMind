import pytest
from parcelkit.discounts import discounted_minor

def test_half():
    assert discounted_minor(1, 5000) == 1
    assert discounted_minor(5, 5000) == 3
def test_unchanged():
    assert discounted_minor(101, 0) == 101
def test_large():
    assert discounted_minor(100000000000001, 5000) == 50000000000001
def test_invalid():
    for args in [(True, 1), (1, False), (-1, 10), (1, 10001)]:
        with pytest.raises(ValueError): discounted_minor(*args)
