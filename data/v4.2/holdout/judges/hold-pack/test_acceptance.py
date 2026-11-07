import json
import pytest
from repomind.context_pack import pack_facts
def test_utf8_and_exact_limit():
    f={'source_id':'s','path':'中文','value':'记忆'}
    size=len(json.dumps([f],ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8'))
    assert pack_facts([f],size)==[f] and pack_facts([f],size-1)==[]
def test_skip_and_continue():
    big={'source_id':'big','path':'p','value':'x'*500};small={'source_id':'s','path':'p'}
    assert pack_facts([big,small],70)==[small]
def test_all_validation():
    for budget in [True,1,-1,2.0,'2']:
        with pytest.raises(ValueError): pack_facts([],budget)
    for fact in [None,{'source_id':'s'},{'source_id':'s','path':'p','x':float('nan')}]:
        with pytest.raises(ValueError): pack_facts([fact],2)
def test_clones_and_citations():
    f={'source_id':'s','path':'p','sha256':'a'*64,'extra':{'x':[1]}};r=pack_facts([f],1000)
    assert r[0]['sha256']=='a'*64;r[0]['extra']['x'].append(2);assert f['extra']['x']==[1]
