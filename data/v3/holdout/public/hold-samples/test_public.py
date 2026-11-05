import pytest
from signalbox.peak_sample import peak_sample

def test_case_1():
    assert peak_sample([2, 9, -1, 3], 2) == 0

def test_case_2():
    assert peak_sample([], 1) is None
