from logging.config import fileConfig

from alembic import context

from app.db import Base, engine
from app import models  # noqa: F401

if context.config.config_file_name:
    fileConfig(context.config.config_file_name)

if context.is_offline_mode():
    from app.config import settings

    context.configure(url=settings.database_url, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    connection = context.config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    else:
        with engine.connect() as connection:
            context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
            with context.begin_transaction():
                context.run_migrations()
