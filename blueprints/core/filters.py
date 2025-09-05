from __future__ import annotations
from datetime import date, time

WEEKDAYS_RU = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

def fmt_time(value: time | None) -> str:
    if not value:
        return ""
    return value.strftime("%H:%M")

def fmt_date(value: date | None) -> str:
    if not value:
        return ""
    return value.strftime("%d.%m.%Y")

def weekday_ru(value: date | int | None) -> str:
    if value is None:
        return ""
    if isinstance(value, int):
        idx = value
    else:
        idx = value.weekday()
    return WEEKDAYS_RU[idx % 7]

def register_filters(app):
    app.add_template_filter(fmt_time, "fmt_time")
    app.add_template_filter(fmt_date, "fmt_date")
    app.add_template_filter(weekday_ru, "weekday_ru")