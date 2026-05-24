from flask import session
from sqlalchemy.exc import SQLAlchemyError

from backend.bcssm_backend.utils import execute_query

import logging
logger = logging.getLogger(__name__)


def get_username_from_request():
    return session.get('user_name')


def get_user_id_from_request():
    user_name = get_username_from_request()
    if not user_name:
        return session.get('user_id')
    try:
        user_rows = execute_query(
            "SELECT u.id FROM users u WHERE u.name = :user_name",
            {'user_name': user_name}
        )
        if user_rows:
            return user_rows[0][0]
    except SQLAlchemyError as e:
        logger.error("Error looking up user ID for %s: %s", user_name, e)
        raise
    return None
