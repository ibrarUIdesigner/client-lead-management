import logging
import os

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

logger = logging.getLogger(__name__)


def create_db_engine(database_url: str) -> Engine:
    connect_args: dict[str, object] = {"connect_timeout": 3}
    kwargs: dict[str, object] = {"pool_pre_ping": True, "connect_args": connect_args}
    if os.environ.get("VERCEL") == "1":
        connect_args["connect_timeout"] = 10
        # Neon transaction pooling rejects server-side prepared statements.
        connect_args["prepare_threshold"] = None
        kwargs["poolclass"] = NullPool
    return create_engine(database_url, **kwargs)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def check_database(engine: Engine) -> bool:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.warning("database_health_check_failed")
        return False
