"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2025-09-05 00:54:25

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Enums
    educationlevel = postgresql.ENUM('VO', 'SPO', name='educationlevel')
    educationlevel.create(op.get_bind(), checkfirst=True)
    buildingtype = postgresql.ENUM('VO', 'SPO', name='buildingtype')
    buildingtype.create(op.get_bind(), checkfirst=True)
    conflictstatus = postgresql.ENUM('OPEN', 'RESOLVED', name='conflictstatus')
    conflictstatus.create(op.get_bind(), checkfirst=True)

    # role
    op.create_table('role',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=50), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_role')),
    sa.UniqueConstraint('name', name=op.f('uq_role_name'))
    )

    # teacher
    op.create_table('teacher',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('full_name', sa.String(length=255), nullable=False),
    sa.Column('short_name', sa.String(length=100), nullable=True),
    sa.Column('external_id', sa.String(length=100), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_teacher')),
    sa.UniqueConstraint('external_id', name=op.f('uq_teacher_external_id'))
    )

    # group
    op.create_table('group',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('code', sa.String(length=50), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('students_count', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('education_level', sa.Enum('VO', 'SPO', name='educationlevel'), nullable=False, server_default='SPO'),
    sa.Column('external_id', sa.String(length=100), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_group')),
    sa.UniqueConstraint('code', name=op.f('uq_group_code')),
    sa.UniqueConstraint('external_id', name=op.f('uq_group_external_id'))
    )
    op.create_index(op.f('ix_group_code'), 'group', ['code'], unique=False)

    # subject
    op.create_table('subject',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('short_name', sa.String(length=100), nullable=True),
    sa.Column('external_id', sa.String(length=100), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_subject')),
    sa.UniqueConstraint('name', name=op.f('uq_subject_name')),
    sa.UniqueConstraint('external_id', name=op.f('uq_subject_external_id'))
    )

    # building
    op.create_table('building',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('address', sa.String(length=255), nullable=True),
    sa.Column('type', sa.Enum('VO', 'SPO', name='buildingtype'), nullable=True),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_building'))
    )

    # room_type
    op.create_table('room_type',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('requires_computers', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    sa.Column('sports', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_room_type')),
    sa.UniqueConstraint('name', name=op.f('uq_room_type_name'))
    )

    # lesson_type
    op.create_table('lesson_type',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_lesson_type')),
    sa.UniqueConstraint('name', name=op.f('uq_lesson_type_name'))
    )

    # time_slot
    op.create_table('time_slot',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('order_no', sa.Integer(), nullable=False),
    sa.Column('start_time', sa.Time(), nullable=False),
    sa.Column('end_time', sa.Time(), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_time_slot')),
    sa.UniqueConstraint('order_no', name=op.f('uq_timeslot_order_no'))
    )
    op.create_index(op.f('ix_timeslot_order_no'), 'time_slot', ['order_no'], unique=False)

    # room
    op.create_table('room',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('building_id', sa.Integer(), nullable=False),
    sa.Column('number', sa.String(length=50), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=False, server_default='0'),
    sa.Column('room_type_id', sa.Integer(), nullable=True),
    sa.Column('computers_count', sa.Integer(), nullable=False, server_default='0'),
    sa.ForeignKeyConstraint(['building_id'], ['building.id'], name=op.f('fk_room_building_id_building'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['room_type_id'], ['room_type.id'], name=op.f('fk_room_room_type_id_room_type'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_room')),
    sa.UniqueConstraint('building_id', 'number', name=op.f('uq_room_building_number'))
    )
    op.create_index(op.f('ix_room_building'), 'room', ['building_id'], unique=False)

    # user
    op.create_table('user',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('updated_at', sa.DateTime(), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id'], name=op.f('fk_user_teacher_id_teacher'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_user')),
    sa.UniqueConstraint('email', name=op.f('uq_user_email'))
    )
    op.create_index(op.f('ix_user_email'), 'user', ['email'], unique=False)

    # availability
    op.create_table('teacher_availability',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=False),
    sa.Column('weekday', sa.Integer(), nullable=False),
    sa.Column('available_from', sa.Time(), nullable=True),
    sa.Column('available_to', sa.Time(), nullable=True),
    sa.Column('is_day_off', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    sa.Column('date_override', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id'], name=op.f('fk_teacher_availability_teacher_id_teacher'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_teacher_availability'))
    )
    op.create_index('ix_availability_teacher_weekday', 'teacher_availability', ['teacher_id', 'weekday'], unique=False)

    # workload_limit
    op.create_table('workload_limit',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=False),
    sa.Column('hours_per_week', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id'], name=op.f('fk_workload_limit_teacher_id_teacher'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_workload_limit')),
    sa.UniqueConstraint('teacher_id', name=op.f('uq_workload_limit_teacher_id'))
    )

    # curriculum
    op.create_table('curriculum',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=False),
    sa.Column('total_hours', sa.Integer(), nullable=False),
    sa.Column('hours_per_week', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['group_id'], ['group.id'], name=op.f('fk_curriculum_group_id_group'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['subject_id'], ['subject.id'], name=op.f('fk_curriculum_subject_id_subject'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_curriculum')),
    sa.UniqueConstraint('group_id', 'subject_id', name=op.f('uq_curriculum_group_subject'))
    )

    # assignment
    op.create_table('assignment',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['group_id'], ['group.id'], name=op.f('fk_assignment_group_id_group'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['subject_id'], ['subject.id'], name=op.f('fk_assignment_subject_id_subject'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id'], name=op.f('fk_assignment_teacher_id_teacher'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_assignment')),
    sa.UniqueConstraint('teacher_id', 'group_id', 'subject_id', name=op.f('uq_assignment_tuple'))
    )

    # lesson_type, time_slot, room, group, subject, teacher already created

    # schedule
    op.create_table('schedule',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('time_slot_id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.Column('subject_id', sa.Integer(), nullable=False),
    sa.Column('lesson_type_id', sa.Integer(), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=False),
    sa.Column('room_id', sa.Integer(), nullable=True),
    sa.Column('is_remote', sa.Boolean(), nullable=False, server_default=sa.text('false')),
    sa.Column('note', sa.Text(), nullable=True),
    sa.ForeignKeyConstraint(['group_id'], ['group.id'], name=op.f('fk_schedule_group_id_group'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['lesson_type_id'], ['lesson_type.id'], name=op.f('fk_schedule_lesson_type_id_lesson_type'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['room_id'], ['room.id'], name=op.f('fk_schedule_room_id_room'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['subject_id'], ['subject.id'], name=op.f('fk_schedule_subject_id_subject'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['teacher_id'], ['teacher.id'], name=op.f('fk_schedule_teacher_id_teacher'), ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['time_slot_id'], ['time_slot.id'], name=op.f('fk_schedule_time_slot_id_time_slot'), ondelete='RESTRICT'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_schedule'))
    )
    op.create_index(op.f('ix_schedule_date'), 'schedule', ['date'], unique=False)
    op.create_index(op.f('ix_schedule_group_id'), 'schedule', ['group_id'], unique=False)
    op.create_index(op.f('ix_schedule_teacher_id'), 'schedule', ['teacher_id'], unique=False)

    # homework
    op.create_table('homework',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('schedule_id', sa.Integer(), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('attachments', sa.JSON(), nullable=True),
    sa.Column('deadline', sa.DateTime(), nullable=True),
    sa.Column('created_by_teacher_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['created_by_teacher_id'], ['teacher.id'], name=op.f('fk_homework_created_by_teacher_id_teacher'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['schedule_id'], ['schedule.id'], name=op.f('fk_homework_schedule_id_schedule'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_homework')),
    sa.UniqueConstraint('schedule_id', name=op.f('uq_homework_schedule_id'))
    )

    # holiday
    op.create_table('holiday',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_holiday')),
    sa.UniqueConstraint('date', name=op.f('uq_holiday_date'))
    )
    op.create_index(op.f('ix_holiday_date'), 'holiday', ['date'], unique=False)

    # conflict
    op.create_table('conflict',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=100), nullable=False),
    sa.Column('schedule_id', sa.Integer(), nullable=True),
    sa.Column('payload_json', sa.JSON(), nullable=True),
    sa.Column('status', sa.Enum('OPEN', 'RESOLVED', name='conflictstatus'), nullable=False, server_default='OPEN'),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('resolved_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['schedule_id'], ['schedule.id'], name=op.f('fk_conflict_schedule_id_schedule'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_conflict'))
    )

    # user_roles association
    op.create_table('user_roles',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('role_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['role_id'], ['role.id'], name=op.f('fk_user_roles_role_id_role'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], name=op.f('fk_user_roles_user_id_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('user_id', 'role_id', name=op.f('pk_user_roles')),
    sa.UniqueConstraint('user_id', 'role_id', name=op.f('uq_user_roles_user_role'))
    )


def downgrade():
    op.drop_table('user_roles')
    op.drop_table('conflict')
    op.drop_index(op.f('ix_holiday_date'), table_name='holiday')
    op.drop_table('holiday')
    op.drop_table('homework')
    op.drop_index(op.f('ix_schedule_teacher_id'), table_name='schedule')
    op.drop_index(op.f('ix_schedule_group_id'), table_name='schedule')
    op.drop_index(op.f('ix_schedule_date'), table_name='schedule')
    op.drop_table('schedule')
    op.drop_table('assignment')
    op.drop_table('curriculum')
    op.drop_table('workload_limit')
    op.drop_index('ix_availability_teacher_weekday', table_name='teacher_availability')
    op.drop_table('teacher_availability')
    op.drop_index(op.f('ix_user_email'), table_name='user')
    op.drop_table('user')
    op.drop_index(op.f('ix_room_building'), table_name='room')
    op.drop_table('room')
    op.drop_index(op.f('ix_timeslot_order_no'), table_name='time_slot')
    op.drop_table('time_slot')
    op.drop_table('lesson_type')
    op.drop_table('room_type')
    op.drop_table('building')
    op.drop_table('subject')
    op.drop_index(op.f('ix_group_code'), table_name='group')
    op.drop_table('group')
    op.drop_table('teacher')
    op.drop_table('role')

    # Drop enums
    conflictstatus = postgresql.ENUM('OPEN', 'RESOLVED', name='conflictstatus')
    conflictstatus.drop(op.get_bind(), checkfirst=True)
    buildingtype = postgresql.ENUM('VO', 'SPO', name='buildingtype')
    buildingtype.drop(op.get_bind(), checkfirst=True)
    educationlevel = postgresql.ENUM('VO', 'SPO', name='educationlevel')
    educationlevel.drop(op.get_bind(), checkfirst=True)
