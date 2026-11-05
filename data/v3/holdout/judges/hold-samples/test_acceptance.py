import pytest
from signalbox.peak_sample import peak_sample

def test_case_1():
    assert peak_sample([-8, -4, -4, -8], 2) == 1

def test_case_2():
    assert peak_sample([1, 2, 1, 2], 2) == 0

def test_case_3():
    with pytest.raises(ValueError): peak_sample([2], True)

def test_case_4():
    with pytest.raises(ValueError): peak_sample([True], 8)
