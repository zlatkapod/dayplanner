from datetime import date, datetime, timedelta
from app import get_sun_times, is_dark_mode, get_configured_tz
import os
from zoneinfo import ZoneInfo

def test_get_configured_tz():
    # Test with TIMEZONE env var
    os.environ["TIMEZONE"] = "Europe/Prague"
    tz = get_configured_tz()
    assert str(tz) == "Europe/Prague"
    
    # Test with TZ env var
    del os.environ["TIMEZONE"]
    os.environ["TZ"] = "America/New_York"
    tz = get_configured_tz()
    assert str(tz) == "America/New_York"
    
    # Cleanup
    del os.environ["TZ"]

from unittest.mock import patch

def test_is_dark_mode():
    # Mock sun times: sunrise 08:00, sunset 18:00
    sunrise = "08:00"
    sunset = "18:00"
    day = date(2026, 2, 10)
    
    # Mock datetime.now to return 07:00 (Dark)
    with patch("app.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 2, 10, 7, 0, tzinfo=ZoneInfo("UTC"))
        mock_datetime.strptime = datetime.strptime # Keep strptime working
        mock_datetime.combine = datetime.combine
        assert is_dark_mode(day, sunrise, sunset) is True
        
    # Mock datetime.now to return 12:00 (Light)
    with patch("app.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 2, 10, 12, 0, tzinfo=ZoneInfo("UTC"))
        mock_datetime.strptime = datetime.strptime
        mock_datetime.combine = datetime.combine
        assert is_dark_mode(day, sunrise, sunset) is False

    # Mock datetime.now to return 20:00 (Dark)
    with patch("app.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2026, 2, 10, 20, 0, tzinfo=ZoneInfo("UTC"))
        mock_datetime.strptime = datetime.strptime
        mock_datetime.combine = datetime.combine
        assert is_dark_mode(day, sunrise, sunset) is True

def test_sun_times_no_coords():
    # Should return (None, None) if LAT/LON not set
    if "LATITUDE" in os.environ: del os.environ["LATITUDE"]
    if "LONGITUDE" in os.environ: del os.environ["LONGITUDE"]
    
    day = date(2026, 2, 10)
    sunrise, sunset = get_sun_times(day)
    assert sunrise is None
    assert sunset is None
