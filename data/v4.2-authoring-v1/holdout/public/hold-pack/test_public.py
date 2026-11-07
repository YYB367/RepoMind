from repomind.context_pack import pack_facts
def test_whole_fact():
    f={'source_id':'s','path':'p','value':'x'};assert pack_facts([f],1000)==[f]
def test_small_budget():
    assert pack_facts([{'source_id':'s','path':'p'}],2)==[]
