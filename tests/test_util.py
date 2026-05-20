import pytest
from gamest.util import format_time


def test_zero_short():
    assert format_time(0) == "0 minutes, 0 seconds"

def test_zero_long():
    assert format_time(0, short=False) == "0 hours, 0 minutes, 0 seconds"

def test_singular_second():
    assert format_time(1) == "0 minutes, 1 second"

def test_singular_minute():
    assert format_time(60) == "1 minute, 0 seconds"

def test_singular_hour_short():
    assert format_time(3600) == "1 hour, 0 minutes, 0 seconds"

def test_all_singular():
    assert format_time(3661) == "1 hour, 1 minute, 1 second"

def test_all_plural():
    assert format_time(7322) == "2 hours, 2 minutes, 2 seconds"

def test_short_hides_zero_hours():
    assert format_time(90) == "1 minute, 30 seconds"

def test_long_shows_zero_hours():
    assert format_time(90, short=False) == "0 hours, 1 minute, 30 seconds"

def test_nonzero_hours_shown_when_short():
    assert format_time(3601) == "1 hour, 0 minutes, 1 second"
