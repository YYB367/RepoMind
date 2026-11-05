import pytest
from relaybox.clip_spans import clip_spans

def test_case_1():
    assert clip_spans([(7, 9), (1, 8), (1, 1)], 0, 8) == [(7, 8), (1, 8)]

def test_case_2():
    with pytest.raises(ValueError): clip_spans([(3, 2)], 2, 2)

def test_case_3():
    with pytest.raises(ValueError): clip_spans([(False, 1)], 0, 2)

def test_case_4():
    with pytest.raises(ValueError): clip_spans([], 5, 4)
