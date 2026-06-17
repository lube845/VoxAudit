"""
Datetime utilities - all datetime operations respect TZ environment variable.
"""
import os
from datetime import datetime, timezone


def get_timezone():
    """Get timezone from TZ environment variable, default to Asia/Shanghai."""
    return os.environ.get('TZ', 'Asia/Shanghai')


def get_current_time():
    """
    Get current time respecting TZ environment variable.
    Returns a timezone-aware datetime in the configured timezone.
    """
    tz_name = get_timezone()
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc
    return datetime.now(tz)


def parse_datetime(dt_string):
    """
    Parse a datetime string and return timezone-aware datetime.
    Handles both naive datetime strings and ISO format.
    """
    if not dt_string:
        return None
    tz_name = get_timezone()
    try:
        from zoneinfo import ZoneInfo
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    if 'Z' in dt_string or '+' in dt_string or dt_string.endswith('+00:00'):
        # ISO format with timezone
        return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))

    # Parse as naive datetime then make it timezone-aware
    from dateutil import parser
    naive_dt = parser.parse(dt_string)
    return naive_dt.replace(tzinfo=tz)


def format_date(dt, fmt='%Y-%m-%d %H:%M:%S'):
    """Format a datetime object respecting TZ."""
    if dt is None:
        return ''
    return dt.strftime(fmt)