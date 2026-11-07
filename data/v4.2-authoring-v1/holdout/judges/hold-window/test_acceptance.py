import pytest
from repomind.review_window import confirmed_window
def row(when): return {'project_id':'RepoMind','status':'confirmed','candidate_id':'c','reviewed_at':when}
def test_timezone_and_edges():
    a=row('2026-11-07T08:00:00+08:00');b=row('2026-11-07T23:59:59.999999Z');c=row('2026-11-08T00:00:00Z')
    assert confirmed_window([a,b,c],'RepoMind','2026-11-07','2026-11-07')==[a,b]
def test_precise_timestamp_range():
    a=row('2026-11-07T03:00:00Z');b=row('2026-11-07T04:00:00Z')
    assert confirmed_window([a,b],'RepoMind','2026-11-07T03:00:00Z','2026-11-07T03:00:00Z')==[a]
def test_invalid_bounds_and_records():
    for lo,hi in [('2026-11-08','2026-11-07'),('2026-11-07T00:00:00','2026-11-08')]:
        with pytest.raises(ValueError): confirmed_window([],'RepoMind',lo,hi)
    for r in [row('2026-11-07'),dict(row('2026-11-07T00:00:00Z'),candidate_id='')]:
        with pytest.raises(ValueError): confirmed_window([r],'RepoMind','2026-11-07','2026-11-07')
def test_independent_copies_and_order():
    a=row('2026-11-07T02:00:00Z');b=row('2026-11-07T01:00:00Z');a['extra']={'x':1}
    r=confirmed_window([a,b],'RepoMind','2026-11-07','2026-11-07');assert r==[a,b]
    r[0]['extra']['x']=2;assert a['extra']['x']==1
