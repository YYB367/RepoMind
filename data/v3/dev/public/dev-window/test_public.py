import pytest
from signalbox.merge_windows import merge_windows

def test_case_1():
    assert merge_windows([(3, 5), (1, 3), (7, 8)]) == [(1, 5), (7, 8)]

def test_case_2():
    assert merge_windows([(4, 4)]) == []
