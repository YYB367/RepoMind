import pytest
from parcelkit.shipping import shipping_fee

def test_first_band():
    assert shipping_fee(1) == 150
    assert shipping_fee(500) == 150
def test_next_band():
    assert shipping_fee(501) == 300
    assert shipping_fee(1000) == 300
def test_types():
    for x in [True, 1.5, '500']:
        with pytest.raises(ValueError): shipping_fee(x)
def test_many():
    assert shipping_fee(5001) == 1650
