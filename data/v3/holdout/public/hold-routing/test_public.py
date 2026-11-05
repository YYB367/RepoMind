import pytest
from signalbox.route_name import route_name

def test_case_1():
    assert route_name("/api/v1/users", {"/": "root", "/api": "api", "/api/v1": "v1"}) == "v1"

def test_case_2():
    assert route_name("/apiv2", {"/api": "api"}) is None
