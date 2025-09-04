from logging.config import fileConfig
from alembic import context
from sqlalchemy import engine_from_config, pool
import os

# Этот конфиг читает alembic.ini
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Поднимаем Flask-приложение и берём metadata у extensions.db
from app import create_app
from extensions import db

app = create_app()
app.app_context().push()
target_metadata = db.metadata

def run_migrations_offline():
    """Запуск в offline-режиме: просто генерим SQL."""
    url = config.get_main_option("sqlalchemy.url") or str(db.engine.url)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # для SQLite безопаснее
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Онлайн-режим: выполняем миграции с подключением к реальной БД."""
    connectable = db.engine

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # для SQLite безопаснее
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
