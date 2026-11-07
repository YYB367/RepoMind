from repomind.maint_keys import explicit_key
def test_one_key():
    assert explicit_key('Use codex.v4_acceptance_path.')==('codex','v4_acceptance_path')
def test_ambiguous():
    assert explicit_key('codex.path and harness.policy') is None
