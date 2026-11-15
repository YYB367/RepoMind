import sys
sys.path.insert(0, "/workspace/src")
from pagination import page, page_query
import pytest

def test_check_01():
    with pytest.raises(ValueError):
        page_query([], {'offset': True})

def test_check_02():
    with pytest.raises(ValueError):
        page_query([], {'offset': False})

def test_check_03():
    with pytest.raises(ValueError):
        page_query([], {'offset': -1})

def test_check_04():
    with pytest.raises(ValueError):
        page_query([], {'offset': 1.5})

def test_check_05():
    with pytest.raises(ValueError):
        page_query([], {'offset': None})

def test_check_06():
    with pytest.raises(ValueError):
        page_query([], {'offset': ''})

def test_check_07():
    with pytest.raises(ValueError):
        page_query([], {'offset': '+1'})

def test_check_08():
    with pytest.raises(ValueError):
        page_query([], {'offset': ' 1'})

def test_check_09():
    with pytest.raises(ValueError):
        page_query([], {'offset': '1.0'})

def test_check_10():
    with pytest.raises(ValueError):
        page_query([], {'offset': '١'})

def test_check_11():
    with pytest.raises(ValueError):
        page_query([], {'limit': True})

def test_check_12():
    with pytest.raises(ValueError):
        page_query([], {'limit': False})

def test_check_13():
    with pytest.raises(ValueError):
        page_query([], {'limit': 0})

def test_check_14():
    with pytest.raises(ValueError):
        page_query([], {'limit': 101})

def test_check_15():
    with pytest.raises(ValueError):
        page_query([], {'limit': 1.5})

def test_check_16():
    with pytest.raises(ValueError):
        page_query([], {'limit': None})

def test_check_17():
    with pytest.raises(ValueError):
        page_query([], {'limit': '-1'})

def test_check_18():
    with pytest.raises(ValueError):
        page_query([], {'limit': ''})

def test_check_19():
    assert page_query([1,2,3], {"offset":10,"limit":100}) == {"items":[],"total":3,"offset":10,"limit":100}

def test_check_20():
    assert page_query([1,2,3], {"offset":"0001","limit":"100"})["items"] == [2,3]

def test_check_21():
    rows=[1,2,3]; params={"offset":"1","limit":"1","q":"x"}
    page_query(rows,params)
    assert rows==[1,2,3] and params=={"offset":"1","limit":"1","q":"x"}

def test_check_22():
    with pytest.raises(ValueError):
        page_query([], None)

def test_check_23():
    with pytest.raises(ValueError):
        page([], True, 50)

def test_check_24():
    with pytest.raises(ValueError):
        page([], 0, 101)