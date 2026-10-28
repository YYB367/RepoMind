import pytest
from parcelkit.sku import normalize_sku

def test_case():
    assert normalize_sku(' ab ') == 'AB'
def test_separators():
    assert normalize_sku(' ab-01/X ') == 'AB-01/X'
def test_zeroes():
    assert normalize_sku('001a') == '001A'
def test_invalid():
    for x in [None, 12, True]:
        with pytest.raises(ValueError): normalize_sku(x)
