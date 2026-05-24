from flask import jsonify, request, session
from markupsafe import escape
from functools import wraps

from sqlalchemy.exc import SQLAlchemyError
from redis.exceptions import RedisError
from backend.globals import cache
from backend.bcssm_backend.utils import (
    get_all_users, get_user_duty, get_users_by_section, execute_query,
    clear_user_cache  # Import cache management function
)
from backend.bcssm_backend.auth import get_username_from_request


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
        """Get users by section - now uses utils function with built-in caching"""
        try:
            section_name = request.args.get('section')
            
            # Use utils function which already has caching built-in
            users = get_users_by_section(section_name)
            
            # Check if it's an error response
            if isinstance(users, dict) and "error" in users:
                app.logger.error(f"Failed to fetch users by section {section_name}: {users['error']}")
                return jsonify({"error": "Failed to fetch users for this section."}), 500
            
            return jsonify({"users": users}), 200
        except SQLAlchemyError as e:
            app.logger.error("Failed to fetch users by section: %s", e)
            return jsonify({"error": "An internal error has occurred."}), 500

    @app.route('/user-duty')
    def user_duty():
        """Get user duty - now accepts username from multiple sources"""
        try:
            # Get username from request (query param, body, header, or session)
            user_name = get_username_from_request()
            
            if not user_name:
                return jsonify({"error": "Username required"}), 400
            
            # Use utils function which already has smart caching with day/cycle keys
            duty_data = get_user_duty(user_name)
            
            return jsonify(duty_data), 200
        except SQLAlchemyError as e:
            app.logger.error("Failed to fetch duty for user: %s", e)
            return jsonify({"error": "An internal error has occurred."}), 500

    @app.route('/select-user', methods=['POST'])
    def select_user():
        """Select user and return user data - modified for persistent auth"""
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

            # Still update session for backward compatibility with other parts of the app
            session.update({
                'user_name': user_name,
                'user_id': user_id,
                'user_section': section_name,
                'is_leader': is_leader
            })

            # Cache user data for quick access with error handling
            try:
                user_cache_key = f'user:data:{user_name}'
                user_data = {
                    'id': user_id,
                    'name': name,
                    'role': role,
                    'section_name': section_name,
                    'is_leader': is_leader
                }
                cache.set(user_cache_key, user_data, timeout=1800)  # 30 minutes
            except RedisError as cache_error:
                # Log cache error but don't fail the request
                app.logger.warning("Failed to cache user data for %s: %s", user_name, cache_error)

            # Return comprehensive user data for frontend
            return jsonify({
                "message": f"User {escape(user_name)} successfully selected.",
                "is_logged_in": True,
                "user_name": user_name,  # Add this for frontend
                "user_section": section_name,
                "role": role,  # Add this for frontend
                "is_leader": is_leader
            }), 200

        except SQLAlchemyError as e:
            app.logger.error("Failed to select user: %s", e)
            return jsonify({"error": "An internal error has occurred."}), 500

    @app.route('/get-selected-user')
    def get_selected_user():
        """Get selected user with cached data - now supports multiple auth methods"""
        # Try to get username from multiple sources
        user_name = get_username_from_request()
        
        if not user_name:
            return jsonify({"user": None})
        
        # Try to get additional user data from cache with error handling
        try:
            user_cache_key = f'user:data:{user_name}'
            user_data = cache.get(user_cache_key)
            
            if user_data:
                return jsonify({
                    "user": user_name,
                    "user_data": user_data
                })
        except RedisError as cache_error:
            # Log cache error but continue with basic response
            app.logger.warning("Failed to retrieve cached user data for %s: %s", user_name, cache_error)
        
        return jsonify({"user": user_name})

    @app.route('/logout', methods=['POST'])
    def logout():
        """Logout user and clear caches"""
        # Get username from multiple sources
        user_name = get_username_from_request()
        
        # Clear user-specific cache entries on logout with error handling
        if user_name:
            try:
                cache_keys_to_delete = [
                    f'user:data:{user_name}',
                    f'user:duty:{user_name}'  # Note: actual keys are more complex with day/cycle
                ]
                for key in cache_keys_to_delete:
                    cache.delete(key)
            except RedisError as cache_error:
                # Log cache error but don't fail logout
                app.logger.warning("Failed to clear cache for user %s: %s", user_name, cache_error)
        
        # Clear session
        session.clear()
        
        return jsonify({"message": "User logged out successfully!"})

    @app.route('/get-users')
    def get_users():
        """Get all users - now uses utils function with built-in caching"""
        try:
            # Use utils function which already has caching built-in
            users = get_all_users()
            
            return jsonify({"users": users}), 200
        except SQLAlchemyError as e:
            app.logger.error("Failed to fetch users: %s", e)
            return jsonify({"error": "An internal error has occurred."}), 500

    @app.route('/api/auth/login', methods=['POST'])
    def api_login():
        """Establish a server-side session for the React login flow."""
        data = request.json or {}
        user_name = data.get('user_name')
        if not user_name:
            return jsonify({'error': 'user_name required'}), 400

        user_name = escape(user_name)

        try:
            user_rows = execute_query(
                "SELECT u.id, u.name, u.role, s.name AS section_name "
                "FROM users u "
                "LEFT JOIN sections s ON u.section_id = s.id "
                "WHERE u.name = :user_name",
                {'user_name': user_name}
            )
        except SQLAlchemyError as e:
            app.logger.error("Login DB error for %s: %s", user_name, e)
            return jsonify({'error': 'An internal error has occurred.'}), 500

        if not user_rows:
            return jsonify({'error': 'Invalid user'}), 401

        user_id, name, role, section_name = user_rows[0]
        is_leader = role in {"Section Leader", "Team Leader", "Admin"}

        session.update({
            'user_name': name,
            'user_id': user_id,
            'user_section': section_name,
            'is_leader': is_leader,
        })

        try:
            user_cache_key = f'user:data:{name}'
            cache.set(user_cache_key, {
                'id': user_id,
                'name': name,
                'role': role,
                'section_name': section_name,
                'is_leader': is_leader,
            }, timeout=1800)
        except Exception as cache_error:
            app.logger.warning("Failed to cache user data for %s: %s", name, cache_error)

        return jsonify({
            'ok': True,
            'user_name': name,
            'role': role,
            'section': section_name,
            'is_leader': is_leader,
        }), 200

    @app.route('/api/auth/logout', methods=['POST'])
    def api_logout():
        """Clear the server-side session and evict user cache."""
        user_name = session.get('user_name')
        if user_name:
            try:
                cache.delete(f'user:data:{user_name}')
            except Exception as e:
                app.logger.warning("Failed to clear cache on logout for %s: %s", user_name, e)
        session.clear()
        return jsonify({'ok': True}), 200

    # Add username validation endpoint for persistent auth
    @app.route('/api/auth/validate')
    def validate_user():
        """Validate if a username is still valid - for persistent auth"""
        user_name = get_username_from_request()
        
        if not user_name:
            return jsonify({"is_valid": False, "error": "No username provided"}), 400
        
        try:
            # Check if user exists in database
            user_rows = execute_query(
                "SELECT u.id, u.name, u.role, s.name AS section_name "
                "FROM users u "
                "LEFT JOIN sections s ON u.section_id = s.id "
                "WHERE u.name = :user_name",
                {'user_name': user_name}
            )
            
            if not user_rows:
                return jsonify({"is_valid": False, "error": "Invalid user"}), 400
            
            user_id, name, role, section_name = user_rows[0]
            is_leader = role in {"Section Leader", "Team Leader", "Admin"}
            
            return jsonify({
                "is_valid": True,
                "user_name": user_name,
                "role": role,
                "section": section_name,
                "is_leader": is_leader
            })
            
        except SQLAlchemyError as e:
            app.logger.error("User validation failed for %s: %s", user_name, e)
            return jsonify({"is_valid": False, "error": "Validation failed"}), 500

    # Enhanced cache stats endpoint
    @app.route('/cache-stats')
    def cache_stats():
        """Enhanced cache status endpoint"""
        try:
            # Test cache operations
            test_key = 'cache:health:check'
            cache.set(test_key, 'ok', timeout=60)
            status = cache.get(test_key)
            cache.delete(test_key)
            
            # Get some cache info
            cache_info = {
                "cache_status": "healthy" if status == 'ok' else "unhealthy",
                "cache_type": "RedisCache",
                "test_result": status,
                "cached_functions": [
                    "get_all_users (15 min)",
                    "get_user_duty (10 min)", 
                    "get_users_by_section (30 min)",
                    "user_data (30 min)"
                ],
                "management": {
                    "clear_users": "Available via clear_user_cache()",
                    "admin_endpoint": "/api/admin/cache/clear"
                }
            }
            
            return jsonify(cache_info)
        except RedisError as e:
            app.logger.error("Cache health check failed: %s", e)
            return jsonify({
                "cache_status": "unhealthy",
                "error": "Cache operations failed"
            }), 500

    # Admin endpoint for clearing user caches
    @app.route('/admin/clear-user-cache', methods=['POST'])
    def clear_user_cache_endpoint():
        """Admin endpoint to clear user-related caches"""
        try:
            # Optional: Add authentication check here
            # if not is_admin_user():
            #     return jsonify({"error": "Admin access required"}), 403
            
            clear_user_cache()
            
            return jsonify({
                "success": True,
                "message": "User caches cleared successfully"
            })
        except RedisError as e:
            app.logger.error("Failed to clear user cache: %s", e)
            return jsonify({
                "success": False,
                "error": "Failed to clear user cache"
            }), 500

    # Endpoint to update user and clear cache
    @app.route('/admin/users/<int:user_id>', methods=['PUT'])
    def update_user(user_id):
        """Update user and clear related caches"""
        try:
            # Optional: Add authentication check
            # if not is_admin_user():
            #     return jsonify({"error": "Admin access required"}), 403
            
            data = request.json
            if not data:
                return jsonify({"error": "No data provided"}), 400
            
            # Your user update logic here
            # update_query = "UPDATE users SET ... WHERE id = :user_id"
            # execute_query(update_query, {"user_id": user_id, **data})
            
            # Clear user caches after successful update
            clear_user_cache()
            
            return jsonify({
                "success": True,
                "message": f"User {user_id} updated successfully"
            })
        except SQLAlchemyError as e:
            app.logger.error("Failed to update user %s: %s", user_id, e)
            return jsonify({
                "success": False,
                "error": "Failed to update user"
            }), 500

    @app.context_processor
    def inject_user_state():
        """Inject user state into templates"""
        user_name = get_username_from_request()
        if user_name:
            # Try to get cached user data
            try:
                user_cache_key = f'user:data:{user_name}'
                user_data = cache.get(user_cache_key)
                if user_data:
                    return {
                        'is_logged_in': True,
                        'user_section': user_data.get('section_name'),
                        'is_leader': user_data.get('is_leader'),
                        'user_id': user_data.get('id')
                    }
            except RedisError as e:
                app.logger.warning("Failed to retrieve cached user data in context processor: %s", e)
            
            # Fallback to session data
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