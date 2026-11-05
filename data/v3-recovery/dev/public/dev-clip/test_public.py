import pytest
from relaybox.clip_spans import clip_spans

def test_case_1():
    assert clip_spans([(-1, 4), (8, 12)], 0, 10) == [(0, 4), (8, 10)]

def test_case_2():
    assert clip_spans([(1, 2)], 2, 3) == []
