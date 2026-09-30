import logging

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)


def create_db_engine(database_url: str) -> Engine:
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 3},
    )


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
