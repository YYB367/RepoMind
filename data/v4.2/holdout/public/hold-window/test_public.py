from repomind.review_window import confirmed_window
def row(**kw): return dict(project_id='RepoMind',status='confirmed',candidate_id='c',reviewed_at='2026-11-07T00:00:00Z',**kw)
def test_date_start_inclusive():
    r=row();assert confirmed_window([r],'RepoMind','2026-11-07','2026-11-07')==[r]
def test_other_status_ignored():
    assert confirmed_window([{'project_id':'Other','status':'confirmed'},{'project_id':'RepoMind','status':'pending'}],'RepoMind','2026-11-07','2026-11-07')==[]
