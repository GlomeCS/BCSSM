import logging
import traceback
from functools import wraps

from flask import g, jsonify, session
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from backend.bcssm_backend.exceptions import (
    AuthenticationError, DatabaseError, NotFoundError, ValidationError
)

logger = logging.getLogger(__name__)


def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_name = session.get('user_name')
        if not user_name:
            return jsonify({'error': 'Authentication required'}), 401
        g.user_name = user_name
        user_id = session.get('user_id')
        if user_id is None:
            from backend.bcssm_backend.utils import get_user_id_by_name
            user_id = get_user_id_by_name(user_name)
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated_function


def handle_route_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except ValidationError as e:
            logger.warning("Validation error in %s: %s", f.__name__, e.message)
            return jsonify({'error': e.message}), 400
        except AuthenticationError as e:
            logger.warning(
                "Authentication error in %s: %s", f.__name__, e.message
            )
            return jsonify({'error': e.message}), 401
        except NotFoundError as e:
            logger.warning("Not found in %s: %s", f.__name__, e.message)
            return jsonify({'error': e.message}), 404
        except (DatabaseError, SQLAlchemyError) as e:
            msg = e.message if isinstance(e, DatabaseError) else str(e)
            logger.error("Database error in %s: %s", f.__name__, msg)
            return jsonify({'error': 'Internal server error'}), 500
        except HTTPException:
            raise
        except Exception as e:
            logger.critical(
                "Unexpected error in %s: %s\n%s",
                f.__name__, e, traceback.format_exc()
            )
            return jsonify({'error': 'Internal server error'}), 500
    return decorated_function
