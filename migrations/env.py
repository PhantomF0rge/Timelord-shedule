from logging.config import fileConfig
from alembic import context
from sqlalchemy import text
import os
import sys

# --- Добавляем КОРЕНЬ репозитория в sys.path, чтобы работал `from app import create_app`
THIS_DIR = os.path.dirname(os.path.abspath(__file__))            # .../migrations
PROJECT_ROOT = os.path.abspath(os.path.join(THIS_DIR, os.pardir))  # корень репозитория
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Конфиг Alembic (читается из alembic.ini)
config = context.config

# Логи Alembic
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# --- Импортируем Flask-приложение и metadata из extensions.db
from app import create_app            # noqa: E402
from extensions import db             # noqa: E402

app = create_app()
app.app_context().push()

# Если в alembic.ini нет sqlalchemy.url — подставим URL из приложения
engine_url = str(db.engine.url)
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", engine_url)

target_metadata = db.metadata

def run_migrations_offline():
    """Offline-режим: генерим SQL без подключения."""
    url = config.get_main_option("sqlalchemy.url") or engine_url
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # безопаснее для SQLite
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    """Online-режим: применяем миграции к реальной БД."""
    connectable = db.engine
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=True,  # безопаснее для SQLite
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
