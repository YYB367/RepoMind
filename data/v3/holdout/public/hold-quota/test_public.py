import pytest
from signalbox.allocate_quota import allocate_quota

def test_case_1():
    assert allocate_quota([1, 1, 1], 2) == [1, 1, 0]

def test_case_2():
    assert allocate_quota([1, 2], 6) == [2, 4]
