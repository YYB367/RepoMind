import pytest
from parcelkit.merges import merge_updates

def test_latest():
    assert merge_updates([{'version': 1, 'value': 'a'}, {'version': 2, 'value': 'b'}]) == {'version': 2, 'value': 'b'}
def test_empty():
    assert merge_updates([]) is None
