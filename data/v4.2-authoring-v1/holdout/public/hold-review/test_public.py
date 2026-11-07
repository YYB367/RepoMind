import pytest
from repomind.review_request import review_identity
def test_valid():
    cid='review-'+'a'*64;assert review_identity({'project':'RepoMind','candidate_id':cid,'revision':2},project='RepoMind')==(cid,2)
def test_scope():
    with pytest.raises(ValueError): review_identity({'project':'Other','candidate_id':'review-'+'a'*64,'revision':1},project='RepoMind')
