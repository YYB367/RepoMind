import pytest
from repomind.query_clock import query_clock
def test_offset():
    r=query_clock('2026-11-07T08:00:00+08:00','2026-11-06',now='2026-11-07T01:00:00Z')
    assert r['as_of'].hour==0 and r['known_at'].day==6
def test_implicit_and_numeric():
    for v in [False,0,1.5,'2026-11-07T00:00:00','bad']:
        with pytest.raises(ValueError): query_clock(v,now='2026-11-07T01:00:00Z')
def test_empty_and_explicit_known():
    r=query_clock('',known_at='2020-01-01',now='2026-11-07T01:00:00Z');assert r['as_of'].year==2026 and r['known_at'].year==2020
def test_always_validate_now():
    with pytest.raises(ValueError): query_clock('2020-01-01','2021-01-01',now='2026-11-07T00:00:00')
