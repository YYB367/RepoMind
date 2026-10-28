import pytest
from parcelkit.inventory import adjust_stock

def test_add():
    assert adjust_stock({'A': 2}, 'A', 3) == {'A': 5}
def test_new():
    assert adjust_stock({}, 'B', 2) == {'B': 2}
