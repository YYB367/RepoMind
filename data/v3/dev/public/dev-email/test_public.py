import pytest
from signalbox.email_host import email_host

def test_case_1():
    assert email_host(" User@Example.ORG  ") == "example.org"

def test_case_2():
    with pytest.raises(ValueError): email_host("missing")
