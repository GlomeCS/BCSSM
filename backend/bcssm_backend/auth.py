from urllib.parse import unquote

from flask import request, session
from markupsafe import escape
from sqlalchemy.exc import SQLAlchemyError

from backend.bcssm_backend.utils import execute_query

import logging
logger = logging.getLogger(__name__)


def get_username_from_request():
    if request.method == 'POST' and request.json:
        username = request.json.get('user_name')
        if username:
            return escape(unquote(username))

    username = request.args.get('user_name') or request.args.get('user')
    if username:
        return escape(unquote(username))

    username = request.headers.get('X-Current-User')
    if username:
        return escape(unquote(username))

    return session.get('user_name')


def get_user_id_from_request():
    user_name = get_username_from_request()
    if user_name:
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

    return session.get('user_id')
