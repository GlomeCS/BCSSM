from datetime import datetime

from flask import redirect, render_template, request, session, url_for

from utils import execute_query


def init_feedback_routes(app):

    @app.route('/devos-feedback', methods=['GET'])
    def devos_feedback():
        # Determine date
        date_str = request.args.get('date')
        if not date_str:
            date_str = datetime.now().strftime('%Y-%m-%d')

        # Collect feedback for all sections from the database
        query = """
        SELECT s.name AS section_name, f.feedback
        FROM sections s
        LEFT JOIN feedback f ON s.id = f.section_id AND f.date = :date;
        """
        try:
            feedback_rows = execute_query(query, {"date": date_str})
            daily_feedback = {row[0]: row[1] for row in feedback_rows}  # Map section name to feedback
        except Exception as e:
            daily_feedback = {}
            app.logger.error(f"Failed to fetch feedback records: {e}")

        # Check if user is logged in and their role
        user_name = session.get('user_name', None)
        user_info = None
        is_leader = False
        if user_name:
            user_info_query = """
            SELECT u.name, u.role, s.name AS section_name
            FROM users u
            LEFT JOIN sections s ON u.section_id = s.id
            WHERE u.name = :user_name;
            """
            user_rows = execute_query(user_info_query, {"user_name": user_name})
            if user_rows:
                user_info = {
                    "name": user_rows[0][0],
                    "role": user_rows[0][1],
                    "section": user_rows[0][2],
                }
                is_leader = user_info["role"] in ["Section Leader", "Team Leader", "Admin"]

        return render_template(
            'devos_feedback.html',
            date_str=date_str,
            daily_feedback=daily_feedback,
            is_logged_in=(user_name is not None),
            user_section=(user_info["section"] if user_info else None),
            is_leader=is_leader
        )
    
    @app.route('/devos-feedback/edit', methods=['GET', 'POST'])
    def devos_feedback_edit():
        user_name = session.get('user_name')
        if not user_name:
            return redirect(url_for('index', next=request.url))
        
        date_str = request.args.get("date")
        section_str = request.args.get("section")
        if not date_str or not section_str:
            return redirect(url_for("devos_feedback"))

        # Fetch user info to determine permissions
        user_info_query = """
        SELECT u.id, u.role, s.name AS section_name
        FROM users u
        LEFT JOIN sections s ON u.section_id = s.id
        WHERE u.name = :user_name;
        """
        user_rows = execute_query(user_info_query, {"user_name": user_name})
        if not user_rows:
            return "User not found", 403

        user_info = {
            "id": user_rows[0][0],
            "role": user_rows[0][1],
            "section": user_rows[0][2],
        }
        is_leader = user_info["role"] in ["Section Leader", "Team Leader"]

        # Check permission
        if not is_leader and user_info["section"] != section_str:
            return "Not authorized", 403

        # Get the section_id for the given section name
        section_query = "SELECT id FROM sections WHERE name = :section_name;"
        section_rows = execute_query(section_query, {"section_name": section_str})
        if not section_rows:
            return "Section not found", 400
        section_id = section_rows[0][0]

        if request.method == 'POST':
            feedback_text = request.form.get('feedback')
            update_query = """
            INSERT INTO feedback (date, section_id, feedback, last_edited_by, last_edited_at)
            VALUES (:date, :section_id, :feedback, :last_edited_by, NOW())
            ON CONFLICT (date, section_id)
            DO UPDATE SET
                feedback = EXCLUDED.feedback,
                last_edited_by = EXCLUDED.last_edited_by,
                last_edited_at = NOW();
            """
            try:
                execute_query(
                    update_query,
                    {
                        "date": date_str,
                        "section_id": section_id,
                        "feedback": feedback_text,
                        "last_edited_by": user_info["id"],
                    },
                )
                return redirect(url_for('devos_feedback', date=date_str))
            except Exception as e:
                app.logger.error(f"Failed to update feedback: {e}")
                return "Error updating feedback", 500

        # GET: show current feedback if any
        feedback_query = """
        SELECT feedback
        FROM feedback
        WHERE date = :date AND section_id = :section_id;
        """
        feedback_rows = execute_query(feedback_query, {"date": date_str, "section_id": section_id})
        existing_text = feedback_rows[0][0] if feedback_rows else ""

        return render_template(
            'devos_feedback_edit.html',
            date_str=date_str,
            section=section_str,
            feedback_text=existing_text
        )