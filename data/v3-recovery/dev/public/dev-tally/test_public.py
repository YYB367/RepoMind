import pytest
from relaybox.status_tally import status_tally

def test_case_1():
    assert status_tally([("A", 2, "closed"), ("A", 1, "open"), ("B", 1, "open")]) == {"open": 1, "closed": 1}

def test_case_2():
    assert status_tally([]) == {"open": 0, "closed": 0}
