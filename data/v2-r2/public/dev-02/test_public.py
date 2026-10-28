import pytest
from parcelkit.shipping import shipping_fee

def test_zero():
    assert shipping_fee(0) == 0
def test_invalid():
    with pytest.raises(ValueError): shipping_fee(-1)
