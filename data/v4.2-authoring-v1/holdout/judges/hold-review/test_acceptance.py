import pytest
from repomind.review_request import review_identity
def base(): return {'project':'RepoMind','candidate_id':'review-'+'a'*64,'revision':1}
def test_strict_revisions():
    for rev in [True,False,0,-1,1.0,'1',None]:
        d=base();d['revision']=rev
        with pytest.raises(ValueError): review_identity(d,project='RepoMind')
def test_shape_and_no_mutation():
    d=base();before=dict(d);review_identity(d,project='RepoMind');assert d==before
    for d in [None,[],dict(base(),value='edit'),{'project':'RepoMind'}]:
        with pytest.raises(ValueError): review_identity(d,project='RepoMind')
def test_bad_id():
    for cid in ['review-'+'A'*64,'review-'+'a'*63,'review-'+'a'*65,'x',True]:
        d=base();d['candidate_id']=cid
        with pytest.raises(ValueError): review_identity(d,project='RepoMind')
def test_literal_project():
    for project in ['repomind','RepoMind ','',None,' ']:
        with pytest.raises(ValueError): review_identity(base(),project=project)
