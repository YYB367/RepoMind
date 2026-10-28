import pytest
from parcelkit.pagination import page_after

def test_stable_equal():
    ids = ['2', '02', '1', '2', '10']
    assert page_after(ids, '2', 10) == ['02', '10']
    assert ids == ['2', '02', '1', '2', '10']
def test_first():
    assert page_after(['10', '2'], None, 1) == ['2']
def test_zero_limit():
    assert page_after(['1'], None, 0) == []
def test_invalid():
    for args in [(['1'], '9', 1), (['x'], None, 1), (['1'], None, True)]:
        with pytest.raises(ValueError): page_after(*args)
