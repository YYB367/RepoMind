import pytest
from parcelkit.merges import merge_updates

def test_conflict():
    with pytest.raises(ValueError): merge_updates([{'version': 1, 'value': 'a'}, {'version': 1, 'value': 'b'}])
def test_duplicates():
    assert merge_updates([{'version': 1, 'value': 'a'}, {'version': 1, 'value': 'a'}]) == {'version': 1, 'value': 'a'}
def test_old_conflict():
    with pytest.raises(ValueError): merge_updates([{'version': 1, 'value': 'a'}, {'version': 2, 'value': 'x'}, {'version': 1, 'value': 'b'}])
def test_copy_and_validation():
    row = {'version': 1, 'value': 'a'}
    assert merge_updates([row]) is not row
    with pytest.raises(ValueError): merge_updates([{'version': True, 'value': 'a'}])
