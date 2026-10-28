import pytest
from parcelkit.timestamps import utc_stamp

def test_offset():
    assert utc_stamp('2026-05-01T12:00:00+02:00') == '2026-05-01T10:00:00Z'
def test_z():
    assert utc_stamp('2026-05-01T10:00:00Z') == '2026-05-01T10:00:00Z'
