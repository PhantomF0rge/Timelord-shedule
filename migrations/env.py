from __future__ import with_statement
import os
from logging.config import fileConfig
from alembic import context
from flask import current_app

config = context.config

cfg_path = config.config_file_name
if cfg_path and os.path.exists(cfg_path):
    fileConfig(cfg_path)

target_metadata = current_app.extensions["migrate"].db.metadata

def run_migrations_offline():
    url = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    connectable = current_app.extensions["migrate"].db.engine
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()