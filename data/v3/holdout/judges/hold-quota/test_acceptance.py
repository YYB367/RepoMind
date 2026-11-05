import pytest
from signalbox.allocate_quota import allocate_quota

def test_case_1():
    assert allocate_quota([1, 3, 6], 4) == [1, 1, 2]

def test_case_2():
    assert allocate_quota([1, 2], 0) == [0, 0]

def test_case_3():
    assert allocate_quota([1, 1], 10**20 + 1) == [5*10**19 + 1, 5*10**19]

def test_case_4():
    with pytest.raises(ValueError): allocate_quota([True, 1], 3)
