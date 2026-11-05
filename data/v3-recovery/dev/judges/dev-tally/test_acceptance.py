import pytest
from relaybox.status_tally import status_tally

def test_case_1():
    assert status_tally([("A", 1, "open"), ("A", 1, "open")]) == {"open": 1, "closed": 0}

def test_case_2():
    with pytest.raises(ValueError): status_tally([("A", 2, "closed"), ("A", 1, "open"), ("A", 1, "closed")])

def test_case_3():
    with pytest.raises(ValueError): status_tally([("A", True, "open")])

def test_case_4():
    with pytest.raises(ValueError): status_tally([("", 1, "closed")])
