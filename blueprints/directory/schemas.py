from __future__ import annotations
from datetime import time
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator

# ---------- Groups ----------
class GroupIn(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: Optional[str] = Field(None, max_length=200)
    students_count: int = Field(ge=0)
    education_level: str = Field(pattern="^(ВО|СПО)$")

class GroupOut(GroupIn):
    id: int

# ---------- Teachers ----------
class TeacherIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    short_name: Optional[str] = Field(None, max_length=50)
    external_id: Optional[str] = Field(None, max_length=50)

class TeacherOut(TeacherIn):
    id: int

# ---------- Subjects ----------
class SubjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    short_name: Optional[str] = Field(None, max_length=50)
    external_id: Optional[str] = Field(None, max_length=50)

class SubjectOut(SubjectIn):
    id: int

# ---------- Buildings ----------
class BuildingIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    address: Optional[str] = Field(None, max_length=200)
    type: str = Field(pattern="^(ВО|СПО)$")

class BuildingOut(BuildingIn):
    id: int

# ---------- Room Types ----------
class RoomTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    requires_computers: bool = False
    sports: bool = False

class RoomTypeOut(RoomTypeIn):
    id: int

# ---------- Rooms ----------
class RoomIn(BaseModel):
    building_id: int
    number: str = Field(min_length=1, max_length=50)
    capacity: int = Field(ge=0)
    room_type_id: int
    computers_count: int = Field(ge=0, default=0)

class RoomOut(RoomIn):
    id: int

# ---------- Lesson Types ----------
class LessonTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)

class LessonTypeOut(LessonTypeIn):
    id: int

# ---------- Time Slots ----------
class TimeSlotIn(BaseModel):
    order_no: int = Field(ge=1)
    start_time: time
    end_time: time

    @model_validator(mode="after")
    def check_range(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be > start_time")
        return self

class TimeSlotOut(TimeSlotIn):
    id: int

# ---------- Assignments (пока только схема OUT для UI-подсказок) ----------
class AssignmentOut(BaseModel):
    id: int
    teacher_id: int
    group_id: int
    subject_id: int
