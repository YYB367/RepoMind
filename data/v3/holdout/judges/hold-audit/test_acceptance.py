import pytest
from signalbox.audit_gaps import audit_gaps

def test_case_1():
    assert audit_gaps([("a", 2), ("a", 4), ("a", 8), ("b", 1), ("b", 3)]) == {"a": [(3, 3), (5, 7)], "b": [(2, 2)]}

def test_case_2():
    assert audit_gaps([("a", 1), ("a", 10**12)]) == {"a": [(2, 10**12 - 1)]}

def test_case_3():
    with pytest.raises(ValueError): audit_gaps([("a", True)])

def test_case_4():
    with pytest.raises(ValueError): audit_gaps([("", 1)])
