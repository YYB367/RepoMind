from repomind.citation_view import citation_view
def test_literal_source():
    f={'source_id':'review-source-one','path':'reports/v4.0/acceptance.json','sha256':'a'*64}
    assert citation_view(f)==dict(f,commit=None)
def test_bad_hash():
    import pytest
    with pytest.raises(ValueError): citation_view({'source_id':'s','path':'p','sha256':'short'})
