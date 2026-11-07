import pytest
from repomind.maint_keys import explicit_key
def test_punctuation_and_unicode():
    assert explicit_key('请查`codex.v4_acceptance_path`。')==('codex','v4_acceptance_path')
def test_non_text():
    for value in [None,True,1,[],{}]:
        with pytest.raises(ValueError): explicit_key(value)
def test_longer_tokens():
    for text in ['a.b.c','9a.b','_a.b','a.9b','a.b_ignored.more','no key']:
        assert explicit_key(text) is None
def test_unique_and_case():
    assert explicit_key('A.b A.b')==('A','b')
    assert explicit_key('A.b a.b') is None
