import pytest
from parcelkit.references import reference_key

def test_common():
    assert reference_key(' ORD42 ') == 'ord42'
def test_invalid():
    with pytest.raises(ValueError): reference_key('   ')
