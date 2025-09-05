"""initial tables

Revision ID: 0001
Revises: 
Create Date: 2025-09-05

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # enums
    education_level = sa.Enum('ВО', 'СПО', name='education_level')
    building_type = sa.Enum('ВО', 'СПО', name='building_type')
    user_role = sa.Enum('ADMIN', 'TEACHER', name='user_role')
    conflict_status = sa.Enum('OPEN', 'RESOLVED', name='conflict_status')

    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect != "sqlite":
        education_level.create(bind, checkfirst=True)
        building_type.create(bind, checkfirst=True)
        user_role.create(bind, checkfirst=True)
        conflict_status.create(bind, checkfirst=True)

    op.create_table('teachers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('full_name', sa.String(), nullable=False),
        sa.Column('short_name', sa.String(), nullable=True),
        sa.Column('external_id', sa.String(), nullable=True),
    )

    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', user_role, nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('1')),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_role', 'users', ['role'])

    op.create_table('groups',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=True),
        sa.Column('students_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('education_level', education_level, nullable=False),
        sa.Column('external_id', sa.String(), nullable=True),
    )
    op.create_index('ix_groups_code', 'groups', ['code'], unique=True)
    op.create_index('ix_groups_education_level', 'groups', ['education_level'])

    op.create_table('subjects',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('short_name', sa.String(), nullable=True),
        sa.Column('external_id', sa.String(), nullable=True),
    )

    op.create_table('buildings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('address', sa.String(), nullable=True),
        sa.Column('type', building_type, nullable=False),
    )

    op.create_table('room_types',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('requires_computers', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('sports', sa.Boolean(), nullable=False, server_default=sa.text('0')),
    )

    op.create_table('lesson_types',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(), nullable=False),
    )

    op.create_table('time_slots',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('order_no', sa.Integer(), nullable=False),
        sa.Column('start_time', sa.Time(), nullable=False),
        sa.Column('end_time', sa.Time(), nullable=False),
    )
    op.create_index('ix_time_slots_order_no', 'time_slots', ['order_no'])

    op.create_table('rooms',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('building_id', sa.Integer(), sa.ForeignKey('buildings.id'), nullable=False),
        sa.Column('number', sa.String(), nullable=False),
        sa.Column('capacity', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('room_type_id', sa.Integer(), sa.ForeignKey('room_types.id'), nullable=False),
        sa.Column('computers_count', sa.Integer(), nullable=False, server_default='0'),
    )
    op.create_unique_constraint('uq_room_building_number', 'rooms', ['building_id','number'])

    op.create_table('teacher_availability',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=False),
        sa.Column('weekday', sa.Integer(), nullable=False),
        sa.Column('available_from', sa.Time(), nullable=True),
        sa.Column('available_to', sa.Time(), nullable=True),
        sa.Column('is_day_off', sa.Boolean(), nullable=False, server_default=sa.text('0')),
    )
    op.create_index('ix_teacher_availability_teacher', 'teacher_availability', ['teacher_id'])

    op.create_table('workload_limits',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=False),
        sa.Column('hours_per_week', sa.Integer(), nullable=False),
    )
    op.create_index('ix_workload_limits_teacher', 'workload_limits', ['teacher_id'])

    op.create_table('curricula',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id'), nullable=False),
        sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('total_hours', sa.Integer(), nullable=False),
        sa.Column('hours_per_week', sa.Integer(), nullable=True),
    )
    op.create_unique_constraint('uq_curriculum_group_subject', 'curricula', ['group_id','subject_id'])

    op.create_table('assignments',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=False),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id'), nullable=False),
        sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id'), nullable=False),
    )
    op.create_unique_constraint('uq_assignment_t_g_s', 'assignments', ['teacher_id','group_id','subject_id'])

    op.create_table('schedules',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('time_slot_id', sa.Integer(), sa.ForeignKey('time_slots.id'), nullable=False),
        sa.Column('group_id', sa.Integer(), sa.ForeignKey('groups.id'), nullable=False),
        sa.Column('subject_id', sa.Integer(), sa.ForeignKey('subjects.id'), nullable=False),
        sa.Column('lesson_type_id', sa.Integer(), sa.ForeignKey('lesson_types.id'), nullable=False),
        sa.Column('teacher_id', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=False),
        sa.Column('room_id', sa.Integer(), sa.ForeignKey('rooms.id'), nullable=True),
        sa.Column('is_remote', sa.Boolean(), nullable=False, server_default=sa.text('0')),
        sa.Column('note', sa.Text(), nullable=True),
    )
    op.create_index('ix_schedules_date', 'schedules', ['date'])
    op.create_index('ix_schedules_group', 'schedules', ['group_id'])
    op.create_index('ix_schedules_teacher', 'schedules', ['teacher_id'])
    op.create_index('ix_schedules_room', 'schedules', ['room_id'])

    op.create_table('homeworks',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('schedule_id', sa.Integer(), sa.ForeignKey('schedules.id'), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('attachments', sa.Text(), nullable=True),
        sa.Column('deadline', sa.DateTime(), nullable=True),
        sa.Column('created_by_teacher_id', sa.Integer(), sa.ForeignKey('teachers.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_homeworks_schedule', 'homeworks', ['schedule_id'])

    op.create_table('holidays',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('date', sa.Date(), nullable=False, unique=True),
        sa.Column('name', sa.String(), nullable=False),
    )
    op.create_index('ix_holidays_date', 'holidays', ['date'])

    op.create_table('conflicts',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('type', sa.String(), nullable=False),
        sa.Column('schedule_id', sa.Integer(), sa.ForeignKey('schedules.id'), nullable=True),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('status', conflict_status, nullable=False, server_default='OPEN'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_conflicts_status', 'conflicts', ['status'])

def downgrade():
    op.drop_index('ix_conflicts_status', table_name='conflicts')
    op.drop_table('conflicts')
    op.drop_index('ix_holidays_date', table_name='holidays')
    op.drop_table('holidays')
    op.drop_index('ix_homeworks_schedule', table_name='homeworks')
    op.drop_table('homeworks')
    op.drop_index('ix_schedules_room', table_name='schedules')
    op.drop_index('ix_schedules_teacher', table_name='schedules')
    op.drop_index('ix_schedules_group', table_name='schedules')
    op.drop_index('ix_schedules_date', table_name='schedules')
    op.drop_table('schedules')
    op.drop_table('assignments')
    op.drop_table('curricula')
    op.drop_index('ix_workload_limits_teacher', table_name='workload_limits')
    op.drop_table('workload_limits')
    op.drop_index('ix_teacher_availability_teacher', table_name='teacher_availability')
    op.drop_table('teacher_availability')
    op.drop_constraint('uq_room_building_number', 'rooms', type_='unique')
    op.drop_table('rooms')
    op.drop_index('ix_time_slots_order_no', table_name='time_slots')
    op.drop_table('time_slots')
    op.drop_table('lesson_types')
    op.drop_table('room_types')
    op.drop_table('buildings')
    op.drop_table('subjects')
    op.drop_index('ix_groups_education_level', table_name='groups')
    op.drop_index('ix_groups_code', table_name='groups')
    op.drop_table('groups')
    op.drop_index('ix_users_role', table_name='users')
    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
    op.drop_table('teachers')

    # drop enums (только не для sqlite)
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.execute('DROP TYPE IF EXISTS education_level')
        op.execute('DROP TYPE IF EXISTS building_type')
        op.execute('DROP TYPE IF EXISTS user_role')
        op.execute('DROP TYPE IF EXISTS conflict_status')
