import pytest
from parcelkit.money import money_minor

def test_rounding():
    assert money_minor('1.005') == 101
    assert money_minor('0.005') == 1
    assert money_minor('-0.005') == -1
def test_decimal():
    from decimal import Decimal
    assert money_minor(Decimal('2.675')) == 268
def test_nonfinite():
    for value in ['NaN', 'Infinity', '-Infinity', True]:
        with pytest.raises(ValueError): money_minor(value)
def test_integer():
    assert money_minor(123) == 12300
