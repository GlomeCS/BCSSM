from functools import wraps
from flask import g, jsonify, session


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
            if user_id is None:
                return jsonify({'error': 'Authentication required'}), 401
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated_function
