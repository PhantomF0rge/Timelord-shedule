from __future__ import annotations
from datetime import time

def ensure_timeslot_range(start_time: time, end_time: time):
    if end_time <= start_time:
        raise ValueError("end_time must be > start_time")
