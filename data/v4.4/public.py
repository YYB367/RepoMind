import sys
sys.path.insert(0, "/workspace/src")
from pagination import page, page_query
import pytest

def test_check_01():
    assert page_query([1,2,3], {}) == {"items":[1,2,3],"total":3,"offset":0,"limit":50}

def test_check_02():
    assert page_query([1,2,3], {"offset":"1","limit":"1"})["items"] == [2]

def test_check_03():
    assert page_query([], {"q":"ignored"})["total"] == 0