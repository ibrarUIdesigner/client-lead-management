import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError

logger = logging.getLogger(__name__)


def flush_or_reject(session: Session) -> None:
    try:
        session.flush()
    except IntegrityError:
        logger.warning("lead_write_rejected")
        raise AppError(
            code="VALIDATION_ERROR",
            message="A value could not be saved. Check the email and website addresses.",
            status_code=422,
        ) from None
