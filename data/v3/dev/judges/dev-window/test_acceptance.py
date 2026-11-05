import pytest
from signalbox.merge_windows import merge_windows

def test_case_1():
    assert merge_windows([(-4, 1), (-3, 0), (0, 7)]) == [(-4, 7)]

def test_case_2():
    with pytest.raises(ValueError): merge_windows([(2, 1)])

def test_case_3():
    with pytest.raises(ValueError): merge_windows([(False, 5)])

def test_case_4():
    rows = [(8, 9), (1, 2)]; assert merge_windows(rows) == [(1, 2), (8, 9)]; assert rows == [(8, 9), (1, 2)]
