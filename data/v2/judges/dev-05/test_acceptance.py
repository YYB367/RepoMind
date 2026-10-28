import pytest
from parcelkit.timestamps import utc_stamp

def test_naive():
    assert utc_stamp('2026-05-01T10:00:00') == '2026-05-01T10:00:00Z'
def test_fraction():
    assert utc_stamp('2026-05-01T10:00:00.999Z') == '2026-05-01T10:00:00Z'
def test_rollover():
    assert utc_stamp('2026-05-01T00:30:00+02:00') == '2026-04-30T22:30:00Z'
def test_invalid():
    for x in ['2026-05-01', 'invalid', None]:
        with pytest.raises(ValueError): utc_stamp(x)
