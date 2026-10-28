import pytest
from parcelkit.references import reference_key

def test_zeroes():
    assert reference_key('0012') == '0012'
def test_unicode():
    assert reference_key(' Straße ') == 'strasse'
def test_punctuation():
    assert reference_key(' A-01/X ') == 'a-01/x'
def test_nonstr():
    for value in [None, 12, True]:
        with pytest.raises(ValueError): reference_key(value)
