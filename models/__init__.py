# models/__init__.py
"""
Агрегатор моделей: даёт единый точный импорт вида
    from models import User, Group, Teacher, Subject, Lesson, TimeSlot, ...
Чтобы избежать падений при отсутствии каких-то файлов, используются try/except.
"""

# Пользователи / роли
try:
    from .user import User
except Exception:
    User = None  # noqa: N816

# Справочники
try:
    from .group import Group
except Exception:
    Group = None  # noqa: N816

try:
    from .teacher import Teacher
except Exception:
    Teacher = None  # noqa: N816

try:
    from .subject import Subject
except Exception:
    Subject = None  # noqa: N816

try:
    from .building import Building
except Exception:
    Building = None  # noqa: N816

try:
    from .room_type import RoomType
except Exception:
    RoomType = None  # noqa: N816

try:
    from .room import Room
except Exception:
    Room = None  # noqa: N816

try:
    from .lesson_type import LessonType
except Exception:
    LessonType = None  # noqa: N816

# Временные слоты (имя файла может отличаться, пробуем варианты)
TimeSlot = None  # noqa: N816
try:
    from .timeslot import TimeSlot as _TS  # предпочтительно
    TimeSlot = _TS
except Exception:
    try:
        from .time_slot import TimeSlot as _TS  # запасной вариант
        TimeSlot = _TS
    except Exception:
        pass

# Учебные сущности
try:
    from .lesson import Lesson
except Exception:
    Lesson = None  # noqa: N816

try:
    from .homework import Homework
except Exception:
    Homework = None  # noqa: N816

__all__ = [
    name for name, val in globals().items()
    if name[0].isupper() and val is not None
]
