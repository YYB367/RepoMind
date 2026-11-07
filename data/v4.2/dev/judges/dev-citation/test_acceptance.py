import pytest
from repomind.citation_view import citation_view
def base(): return {'source_id':'s','path':'p','sha256':'b'*64,'commit':'c'*40}
def test_full_commits_and_extra():
    f=base();f['commit']='f'*64;f['other']={'secret':'not a real key'}
    r=citation_view(f);assert set(r)=={'source_id','path','sha256','commit'} and r['commit']=='f'*64
def test_invalid_fields():
    for key,value in [('source_id',' '),('path',None),('sha256','A'*64),('commit',True),('commit','d'*41)]:
        f=base();f[key]=value
        with pytest.raises(ValueError): citation_view(f)
def test_literal_and_no_mutation():
    f=base();f['path']='资料/<tag>.md';r=citation_view(f);r['path']='elsewhere';assert f['path']=='资料/<tag>.md'
def test_non_dict_and_missing():
    for f in [None,[],{},True]:
        with pytest.raises(ValueError): citation_view(f)
