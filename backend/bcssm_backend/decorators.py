import hmac
import logging
import os
import traceback
from functools import wraps

from flask import g, jsonify, request, session
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import SQLAlchemyError

from backend.bcssm_backend.constants import ELEVATED_ROLES
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
        g.user_role = session.get('user_role')
        g.user_section = session.get('user_section')

        user_id = session.get('user_id')
        if user_id is None:
            from backend.bcssm_backend.utils import get_user_id_by_name
            user_id = get_user_id_by_name(user_name)
            if user_id is None:
                return jsonify({'error': 'Authentication required'}), 401
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated_function


def require_role(*roles):
    """Generic role gate. Must be stacked after @require_auth."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if g.user_role not in roles:
                return jsonify({'error': 'Forbidden'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_feedback_edit_permission(f):
    """Domain decorator for Devos feedback editing. Stacks after @require_auth."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user_role in ELEVATED_ROLES:
            return f(*args, **kwargs)
        target_section = request.args.get('section')
        if target_section and g.user_section == target_section:
            return f(*args, **kwargs)
        return jsonify({'error': 'Forbidden'}), 403
    return decorated_function


def require_admin(f):
    """Admin gate: accepts session role 'Admin' OR a valid X-Admin-Secret HMAC header."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.get('user_role') == 'Admin' or session.get('user_role') == 'Admin':
            return f(*args, **kwargs)
        admin_secret = os.getenv('ADMIN_SECRET', '').strip()
        provided = request.headers.get('X-Admin-Secret', '').strip()
        if admin_secret and provided and hmac.compare_digest(provided, admin_secret):
            return f(*args, **kwargs)
        logger.warning("Unauthorized admin access attempt on %s", request.path)
        return jsonify({'error': 'Unauthorized'}), 403
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
