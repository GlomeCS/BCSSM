import logging
from flask import jsonify, session

from backend.bcssm_backend.utils import get_all_sections_with_users, get_users_by_section_optimized

logger = logging.getLogger(__name__)

def init_users_sections_routes(app):
    @app.route('/api/users/by-section', methods=['GET'])
    def get_users_by_section_route():
        """
        Get all users grouped by their sections
        Returns: JSON with sections and their users
        """
        
        user_name = session.get('user_name')
        if not user_name:
            return jsonify({'error': 'User not authenticated'}), 401
            
        try:
            logger.info("Fetching users grouped by section")
            
            # Get all sections with their users
            sections_data = get_all_sections_with_users()
            
            if isinstance(sections_data, dict) and "error" in sections_data:
                logger.error("Error fetching sections data: %s", sections_data["error"])
                return jsonify({"error": sections_data["error"]}), 500
            
            # Format response
            response = {
                "sections": sections_data,
                "total_users": sum(len(section["users"]) for section in sections_data),
                "total_sections": len(sections_data)
            }
            
            logger.info("Successfully fetched %d sections with %d total users", 
                       response["total_sections"], response["total_users"])
            
            return jsonify(response)
            
        except Exception as e:
            logger.error("Failed to fetch users by section: %s", e)
            return jsonify({"error": "Failed to fetch users by section"}), 500

    @app.route('/api/users/section/<section_name>', methods=['GET'])
    def get_section_users_route(section_name):
        """
        Get users for a specific section
        """
        user_name = session.get('user_name')
        if not user_name:
            return jsonify({'error': 'User not authenticated'}), 401
            
        try:
            logger.info("Fetching users for section: %s", section_name)
            
            users = get_users_by_section_optimized(section_name)
            
            if isinstance(users, dict) and "error" in users:
                logger.error("Error fetching users for section %s: %s", section_name, users["error"])
                return jsonify({"error": users["error"]}), 500
            
            response = {
                "section": section_name,
                "users": users,
                "user_count": len(users)
            }
            
            return jsonify(response)
            
        except Exception as e:
            logger.error("Failed to fetch users for section %s: %s", section_name, e)
            return jsonify({"error": f"Failed to fetch users for section {section_name}"}), 500