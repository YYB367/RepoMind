import pytest
from parcelkit.sku import normalize_sku

def test_digits():
    assert normalize_sku('123') == '123'
def test_empty():
    with pytest.raises(ValueError): normalize_sku(' ')
