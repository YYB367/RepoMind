import pytest
from signalbox.email_host import email_host

def test_case_1():
    assert email_host("a@HOST") == "host"

def test_case_2():
    with pytest.raises(ValueError): email_host("a@b@c")

def test_case_3():
    with pytest.raises(ValueError): email_host("a @host")

def test_case_4():
    with pytest.raises(ValueError): email_host(42)
