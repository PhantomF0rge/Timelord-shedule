from datetime import datetime, time, date
from enum import Enum as PyEnum

from sqlalchemy import (
    Enum, ForeignKey, UniqueConstraint, Index, Boolean, Date, DateTime, Time,
    Integer, String, Text, JSON
)
from sqlalchemy.orm import relationship, Mapped, mapped_column

from extensions import db

# ---------- Enums ----------
class EducationLevel(PyEnum):
    VO = "VO"   # Высшее
    SPO = "SPO" # Среднее проф.

class BuildingType(PyEnum):
    VO = "VO"
    SPO = "SPO"

class ConflictStatus(PyEnum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"


# ---------- Association Tables ----------
user_roles = db.Table(
    "user_roles",
    db.Column("user_id", db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True),
    db.Column("role_id", db.Integer, db.ForeignKey("role.id", ondelete="CASCADE"), primary_key=True),
    db.UniqueConstraint("user_id", "role_id", name="uq_user_roles_user_role"),
)


# ---------- Core Entities ----------
class Role(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False)

    def __repr__(self):
        return f"<Role {self.name}>"


class User(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(db.String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(db.String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(db.Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teacher.id", ondelete="SET NULL"), nullable=True)

    roles = relationship("Role", secondary=user_roles, backref="users")

    def __repr__(self):
        return f"<User {self.email}>"


class Teacher(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    short_name: Mapped[str | None] = mapped_column(db.String(100))
    external_id: Mapped[str | None] = mapped_column(db.String(100), unique=True)

    availabilities = relationship("TeacherAvailability", back_populates="teacher", cascade="all, delete-orphan")
    workload_limit = relationship("WorkloadLimit", back_populates="teacher", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Teacher {self.full_name}>"


class TeacherAvailability(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher.id", ondelete="CASCADE"), nullable=False, index=True)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Mon .. 6=Sun
    available_from: Mapped[time | None] = mapped_column(Time)
    available_to: Mapped[time | None] = mapped_column(Time)
    is_day_off: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # Optional date-specific override (if set, applies to that exact date)
    date_override: Mapped[date | None] = mapped_column(Date, nullable=True)

    teacher = relationship("Teacher", back_populates="availabilities")

    __table_args__ = (
        Index("ix_availability_teacher_weekday", "teacher_id", "weekday"),
    )


class WorkloadLimit(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher.id", ondelete="CASCADE"), unique=True, nullable=False)
    hours_per_week: Mapped[int] = mapped_column(Integer, nullable=False)

    teacher = relationship("Teacher", back_populates="workload_limit")


class Group(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(db.String(50), unique=True, nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(db.String(255))
    students_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    education_level: Mapped[EducationLevel] = mapped_column(Enum(EducationLevel), nullable=False, default=EducationLevel.SPO)
    external_id: Mapped[str | None] = mapped_column(db.String(100), unique=True)

    def __repr__(self):
        return f"<Group {self.code}>"


class Subject(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), nullable=False, unique=True)
    short_name: Mapped[str | None] = mapped_column(db.String(100))
    external_id: Mapped[str | None] = mapped_column(db.String(100), unique=True)


class Building(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(db.String(255))
    type: Mapped[BuildingType | None] = mapped_column(Enum(BuildingType))


class RoomType(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False, unique=True)
    requires_computers: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sports: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class Room(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    building_id: Mapped[int] = mapped_column(ForeignKey("building.id", ondelete="RESTRICT"), nullable=False)
    number: Mapped[str] = mapped_column(db.String(50), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    room_type_id: Mapped[int | None] = mapped_column(ForeignKey("room_type.id", ondelete="SET NULL"))
    computers_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    building = relationship("Building")
    room_type = relationship("RoomType")

    __table_args__ = (
        UniqueConstraint("building_id", "number", name="uq_room_building_number"),
        Index("ix_room_building", "building_id"),
    )


class LessonType(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(db.String(100), nullable=False, unique=True)


class TimeSlot(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    order_no: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[time] = mapped_column(Time, nullable=False)
    end_time: Mapped[time] = mapped_column(Time, nullable=False)

    __table_args__ = (
        UniqueConstraint("order_no", name="uq_timeslot_order_no"),
        Index("ix_timeslot_order_no", "order_no"),
    )


class Curriculum(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subject.id", ondelete="CASCADE"), nullable=False)
    total_hours: Mapped[int] = mapped_column(Integer, nullable=False)
    hours_per_week: Mapped[int | None] = mapped_column(Integer)

    group = relationship("Group")
    subject = relationship("Subject")

    __table_args__ = (
        UniqueConstraint("group_id", "subject_id", name="uq_curriculum_group_subject"),
    )


class Assignment(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher.id", ondelete="CASCADE"), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("group.id", ondelete="CASCADE"), nullable=False)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subject.id", ondelete="CASCADE"), nullable=False)

    teacher = relationship("Teacher")
    group = relationship("Group")
    subject = relationship("Subject")

    __table_args__ = (
        UniqueConstraint("teacher_id", "group_id", "subject_id", name="uq_assignment_tuple"),
    )


class Schedule(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    time_slot_id: Mapped[int] = mapped_column(ForeignKey("time_slot.id", ondelete="RESTRICT"), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("group.id", ondelete="RESTRICT"), nullable=False, index=True)
    subject_id: Mapped[int] = mapped_column(ForeignKey("subject.id", ondelete="RESTRICT"), nullable=False)
    lesson_type_id: Mapped[int] = mapped_column(ForeignKey("lesson_type.id", ondelete="RESTRICT"), nullable=False)
    teacher_id: Mapped[int] = mapped_column(ForeignKey("teacher.id", ondelete="RESTRICT"), nullable=False, index=True)
    room_id: Mapped[int | None] = mapped_column(ForeignKey("room.id", ondelete="SET NULL"))
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)

    time_slot = relationship("TimeSlot")
    group = relationship("Group")
    subject = relationship("Subject")
    lesson_type = relationship("LessonType")
    teacher = relationship("Teacher")
    room = relationship("Room")


class Homework(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    schedule_id: Mapped[int] = mapped_column(ForeignKey("schedule.id", ondelete="CASCADE"), nullable=False, unique=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    attachments: Mapped[dict | None] = mapped_column(JSON)  # store list of files/links, etc.
    deadline: Mapped[datetime | None] = mapped_column(DateTime)
    created_by_teacher_id: Mapped[int | None] = mapped_column(ForeignKey("teacher.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    schedule = relationship("Schedule")
    created_by_teacher = relationship("Teacher")


class Holiday(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    date: Mapped[date] = mapped_column(Date, nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(db.String(255), nullable=False)


class Conflict(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(db.String(100), nullable=False)
    schedule_id: Mapped[int | None] = mapped_column(ForeignKey("schedule.id", ondelete="SET NULL"))
    payload_json: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[ConflictStatus] = mapped_column(Enum(ConflictStatus), default=ConflictStatus.OPEN, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)

    schedule = relationship("Schedule")
