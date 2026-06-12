from functools import wraps
from flask import g, jsonify, session


def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_name = session.get('user_name')
        if not user_name:
            return jsonify({'error': 'Authentication required'}), 401
        g.user_name = user_name
        g.user_id = session.get('user_id')
        return f(*args, **kwargs)
    return decorated_function
