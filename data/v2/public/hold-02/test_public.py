import pytest
from parcelkit.pagination import page_after

def test_order():
    assert page_after(['10', '2', '1'], '1', 2) == ['2', '10']
def test_empty():
    assert page_after([], None, 2) == []
