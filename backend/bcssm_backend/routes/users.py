from flask import jsonify, request, session
from markupsafe import escape
from functools import wraps

from backend.globals import cache
from backend.bcssm_backend.utils import (get_all_users, get_user_duty,
                               get_users_by_section, execute_query)


def validate_params(*required_params):
    """Decorator to validate required parameters in request"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            missing = []
            for param in required_params:
                # For GET requests, check query parameters
                # For POST requests, check JSON body
                if request.method == 'GET':
                    if param not in request.args:
                        missing.append(param)
                else:
                    request_json = request.json or {}
                    if param not in request_json:
                        missing.append(param)
                        
            if missing:
                return jsonify({"error": f"Missing parameters: {', '.join(missing)}"}), 400
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def init_users_routes(app):

    @app.route('/users-by-section')
    @validate_params('section')
    def users_by_section():
        try:
            section_name = request.args.get('section')
            cache_key = f'users:section:{section_name}'
            
            users = cache.get(cache_key)
            if not users:
                users = get_users_by_section(section_name)
                cache.set(cache_key, users, timeout=600)  # 10 minutes
            
            return jsonify({"users": users}), 200
        except Exception as e:
            app.logger.error(f"Failed to fetch users by section: {str(e)}")
            return jsonify({"error": "An internal error has occurred."}), 500

    @app.route('/user-duty')
    @validate_params('user')
    def user_duty():
        try:
            user_name = request.args.get('user')
            cache_key = f'user:duty:{user_name}'
            
            duty_data = cache.get(cache_key)
            if not duty_data:
                duty_data = get_user_duty(user_name)
                cache.set(cache_key, duty_data, timeout=600)  # 10 minutes
            
            return jsonify(duty_data), 200
        except Exception as e:
            app.logger.error(f"Failed to fetch duty for user {user_name}: {str(e)}")
            return jsonify({"error": "An internal error has occurred."}), 500

    @app.route('/select-user', methods=['POST'])
    def select_user():
        try:
            user_name = request.json.get('user_name')
            if not user_name:
                return jsonify({"error": "User name required."}), 400

            user_name = escape(user_name)

            # Single query to validate and fetch user data
            user_rows = execute_query(
                "SELECT u.id, u.name, u.role, s.name AS section_name "
                "FROM users u "
                "LEFT JOIN sections s ON u.section_id = s.id "
                "WHERE u.name = :user_name",
                {'user_name': user_name}
            )

            if not user_rows:
                app.logger.warning(f"Invalid user selection attempt: {user_name}")
                return jsonify({'error': 'Invalid user selected'}), 400

            user_id, name, role, section_name = user_rows[0]
            is_leader = role in {"Section Leader", "Team Leader", "Admin"}

            # Batch session updates
            session.update({
                'user_name': user_name,
                'user_id': user_id,
                'user_section': section_name,
                'is_leader': is_leader
            })

            # Cache user data for quick access
            user_cache_key = f'user:data:{user_name}'
            user_data = {
                'id': user_id,
                'name': name,
                'role': role,
                'section_name': section_name,
                'is_leader': is_leader
            }
            cache.set(user_cache_key, user_data, timeout=1800)  # 30 minutes

            return jsonify({
                "message": f"User {escape(user_name)} successfully selected.",
                "is_logged_in": True,
                "user_section": section_name,
                "is_leader": is_leader
            }), 200

        except Exception as e:
            app.logger.error(f"Failed to select user: {str(e)}")
            return jsonify({"error": "An internal error has occurred."}), 500

    @app.route('/get-selected-user')
    def get_selected_user():
        user_name = session.get('user_name')
        if not user_name:
            return jsonify({"user": None})
        
        # Try to get additional user data from cache
        user_cache_key = f'user:data:{user_name}'
        user_data = cache.get(user_cache_key)
        
        if user_data:
            return jsonify({
                "user": user_name,
                "user_data": user_data
            })
        
        return jsonify({"user": user_name})

    @app.route('/logout', methods=['POST'])
    def logout():
        user_name = session.get('user_name')
        
        # Clear user-specific cache entries on logout
        if user_name:
            cache_keys_to_delete = [
                f'user:data:{user_name}',
                f'user:duty:{user_name}'
            ]
            for key in cache_keys_to_delete:
                cache.delete(key)
        
        # Clear session
        session.clear()
        
        return jsonify({"message": "User logged out successfully!"})

    @app.route('/get-users')
    def get_users():
        try:
            cache_key = 'users:all:active'
            users = cache.get(cache_key)
            
            if not users:
                users = get_all_users()
                cache.set(cache_key, users, timeout=900)  # 15 minutes

            return jsonify({"users": users}), 200
        except Exception as e:
            app.logger.error(f"Failed to fetch users: {str(e)}")
            return jsonify({"error": "An internal error has occurred."}), 500

    @app.route('/cache-stats')
    def cache_stats():
        """Development endpoint to check cache status"""
        try:
            # This is a simple check - Redis would need specific commands for detailed stats
            test_key = 'cache:health:check'
            cache.set(test_key, 'ok', timeout=60)
            status = cache.get(test_key)
            cache.delete(test_key)
            
            return jsonify({
                "cache_status": "healthy" if status == 'ok' else "unhealthy",
                "cache_type": "RedisCache"
            })
        except Exception as e:
            app.logger.error(f"Cache health check failed: {str(e)}")
            return jsonify({
                "cache_status": "unhealthy",
                "error": "An internal error has occurred."
            }), 500

    @app.route('/clear-cache', methods=['POST'])
    def clear_cache():
        """Administrative endpoint to clear cache"""
        try:
            cache.clear()
            return jsonify({"message": "Cache cleared successfully"})
        except Exception as e:
            app.logger.error(f"Failed to clear cache: {str(e)}")
            return jsonify({"error": "Failed to clear cache"}), 500

    @app.context_processor
    def inject_user_state():
        user_name = session.get('user_name')
        if user_name:
            return {
                'is_logged_in': True,
                'user_section': session.get('user_section'),
                'is_leader': session.get('is_leader'),
                'user_id': session.get('user_id')
            }
        else:
            return {
                'is_logged_in': False,
                'user_section': None,
                'is_leader': False,
                'user_id': None
            }