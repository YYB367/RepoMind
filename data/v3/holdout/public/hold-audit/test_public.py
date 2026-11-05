import pytest
from signalbox.audit_gaps import audit_gaps

def test_case_1():
    assert audit_gaps([("a", 5), ("a", 2), ("b", 9)]) == {"a": [(3, 4)]}

def test_case_2():
    assert audit_gaps([("a", 5), ("a", 5), ("a", 6)]) == {}
