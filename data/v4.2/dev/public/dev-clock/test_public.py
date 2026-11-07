from repomind.query_clock import query_clock
def test_default():
    r=query_clock(None,now='2026-11-07T01:00:00Z');assert r['as_of']==r['known_at']
def test_date():
    r=query_clock('2026-11-06',now='2026-11-07T01:00:00Z');assert r['as_of'].isoformat()=='2026-11-06T23:59:59.999999+00:00'
