import pytest
from signalbox.route_name import route_name

def test_case_1():
    assert route_name("/API/x", {"/api": "api", "/": "fallback"}) == "fallback"

def test_case_2():
    assert route_name("/api", {"/api": "direct", "/api/v1": "deep"}) == "direct"

def test_case_3():
    assert route_name("/", {"/": "root"}) == "root"

def test_case_4():
    assert route_name("/x", {}) is None
