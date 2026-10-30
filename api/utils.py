from datetime import date, datetime, time, timedelta

from fastapi import HTTPException


def date_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    """Turn an inclusive [start, end] date range into datetime bounds [low, high)."""
    if end < start:
        raise HTTPException(status_code=400, detail="end must be on or after start")
    return datetime.combine(start, time.min), datetime.combine(end + timedelta(days=1), time.min)
