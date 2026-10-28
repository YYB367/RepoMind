import pytest
from parcelkit.inventory import adjust_stock

def test_no_mutation():
    original = {'A': 2, 'B': 3}
    result = adjust_stock(original, 'A', -1)
    assert original == {'A': 2, 'B': 3}
    assert result == {'A': 1, 'B': 3} and result is not original
def test_reject_atomic():
    original = {'A': 1}
    with pytest.raises(ValueError): adjust_stock(original, 'A', -2)
    assert original == {'A': 1}
def test_missing_negative():
    with pytest.raises(ValueError): adjust_stock({}, 'X', -1)
def test_bool():
    with pytest.raises(ValueError): adjust_stock({}, 'X', True)
