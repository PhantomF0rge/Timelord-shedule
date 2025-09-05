from __future__ import annotations
from datetime import datetime, time, date
from flask_login import UserMixin
from sqlalchemy import Enum, UniqueConstraint, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from extensions import db

# Enums
EducationLevelEnum = Enum("ВО", "СПО", name="education_level")
BuildingTypeEnum = Enum("ВО", "СПО", name="building_type")
UserRoleEnum = Enum("ADMIN", "TEACHER", name="user_role")
ConflictStatusEnum = Enum("OPEN", "RESOLVED", name="conflict_status")

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    password_hash: Mapped[str]
    role: Mapped[str] = mapped_column(UserRoleEnum, index=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"), nullable=True)

    teacher: Mapped["Teacher"] = relationship(back_populates="user", uselist=False)

class Teacher(db.Model):
    __tablename__ = "teachers"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str]
    short_name: Mapped[str | None]
    external_id: Mapped[str | None]

    user: Mapped["User"] = relationship(back_populates="teacher", uselist=False)
    availabilities: Mapped[list["TeacherAvailability"]] = relationship(back_populates="teacher")
    workload_limits: Mapped[list["WorkloadLimit"]] = relationship(back_populates="teacher")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="teacher")

class TeacherAvailability(db.Model):
    __tablename__ = "teacher_availability"
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), index=True)
    weekday: Mapped[int]  # 0=Mon ... 6=Sun
    available_from: Mapped[time | None]
    available_to: Mapped[time | None]
    is_day_off: Mapped[bool] = mapped_column(default=False)

    teacher: Mapped["Teacher"] = relationship(back_populates="availabilities")

class WorkloadLimit(db.Model):
    __tablename__ = "workload_limits"
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), index=True)
    hours_per_week: Mapped[int]

    teacher: Mapped["Teacher"] = relationship(back_populates="workload_limits")

class Group(db.Model):
    __tablename__ = "groups"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(unique=True, index=True)
    name: Mapped[str | None]
    students_count: Mapped[int] = mapped_column(default=0)
    education_level: Mapped[str] = mapped_column(EducationLevelEnum, index=True)
    external_id: Mapped[str | None]

    schedules: Mapped[list["Schedule"]] = relationship(back_populates="group")
    curricula: Mapped[list["Curriculum"]] = relationship(back_populates="group")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="group")

class Subject(db.Model):
    __tablename__ = "subjects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    short_name: Mapped[str | None]
    external_id: Mapped[str | None]

    schedules: Mapped[list["Schedule"]] = relationship(back_populates="subject")
    curricula: Mapped[list["Curriculum"]] = relationship(back_populates="subject")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="subject")

class Building(db.Model):
    __tablename__ = "buildings"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    address: Mapped[str | None]
    type: Mapped[str] = mapped_column(BuildingTypeEnum)

    rooms: Mapped[list["Room"]] = relationship(back_populates="building")

class RoomType(db.Model):
    __tablename__ = "room_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    requires_computers: Mapped[bool] = mapped_column(default=False)
    sports: Mapped[bool] = mapped_column(default=False)

    rooms: Mapped[list["Room"]] = relationship(back_populates="room_type")

class Room(db.Model):
    __tablename__ = "rooms"
    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("buildings.id"), index=True)
    number: Mapped[str]
    capacity: Mapped[int] = mapped_column(default=0)
    room_type_id: Mapped[int] = mapped_column(ForeignKey("room_types.id"), index=True)
    computers_count: Mapped[int] = mapped_column(default=0)

    building: Mapped["Building"] = relationship(back_populates="rooms")
    room_type: Mapped["RoomType"] = relationship(back_populates="rooms")
    schedules: Mapped[list["Schedule"]] = relationship(back_populates="room")

    __table_args__ = (UniqueConstraint("building_id", "number", name="uq_room_building_number"),)

class LessonType(db.Model):
    __tablename__ = "lesson_types"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]

    schedules: Mapped[list["Schedule"]] = relationship(back_populates="lesson_type")

class TimeSlot(db.Model):
    __tablename__ = "time_slots"
    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[int] = mapped_column(index=True)
    start_time: Mapped[time]
    end_time: Mapped[time]

    schedules: Mapped[list["Schedule"]] = relationship(back_populates="time_slot")

class Curriculum(db.Model):
    __tablename__ = "curricula"
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    total_hours: Mapped[int]
    hours_per_week: Mapped[int | None]

    group: Mapped["Group"] = relationship(back_populates="curricula")
    subject: Mapped["Subject"] = relationship(back_populates="curricula")

    __table_args__ = (UniqueConstraint("group_id", "subject_id", name="uq_curriculum_group_subject"),)

class Assignment(db.Model):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)

    teacher: Mapped["Teacher"] = relationship()
    group: Mapped["Group"] = relationship(back_populates="assignments")
    subject: Mapped["Subject"] = relationship(back_populates="assignments")

    __table_args__ = (UniqueConstraint("teacher_id", "group_id", "subject_id", name="uq_assignment_t_g_s"),)

class Schedule(db.Model):
    __tablename__ = "schedules"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(index=True)
    time_slot_id: Mapped[int] = mapped_column(ForeignKey("time_slots.id"), index=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id"), index=True)
    lesson_type_id: Mapped[int] = mapped_column(ForeignKey("lesson_types.id"), index=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teachers.id"), index=True)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("rooms.id"), nullable=True, index=True)
    is_remote: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str | None]

    time_slot: Mapped["TimeSlot"] = relationship(back_populates="schedules")
    group: Mapped["Group"] = relationship(back_populates="schedules")
    subject: Mapped["Subject"] = relationship(back_populates="schedules")
    lesson_type: Mapped["LessonType"] = relationship(back_populates="schedules")
    teacher: Mapped["Teacher"] = relationship(back_populates="schedules")
    room: Mapped["Room"] = relationship(back_populates="schedules")
    homeworks: Mapped[list["Homework"]] = relationship(back_populates="schedule")

class Homework(db.Model):
    __tablename__ = "homeworks"
    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedules.id"), index=True)
    text: Mapped[str]
    attachments: Mapped[str | None]  # JSON as string for simplicity
    deadline: Mapped[datetime | None]
    created_by_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teachers.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    schedule: Mapped["Schedule"] = relationship(back_populates="homeworks")

class Holiday(db.Model):
    __tablename__ = "holidays"
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(unique=True, index=True)
    name: Mapped[str]

class Conflict(db.Model):
    __tablename__ = "conflicts"
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str]
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("schedules.id"), nullable=True)
    payload_json: Mapped[str | None]
    status: Mapped[str] = mapped_column(ConflictStatusEnum, default="OPEN", index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    resolved_at: Mapped[datetime | None]
