import logging

import backend.bcssm_backend.db_utils as _db
from backend.bcssm_backend.cache_utils import cached_result, clear_group
from backend.bcssm_backend.exceptions import ValidationError

logger = logging.getLogger(__name__)


@cached_result('feedback:dates:all',
               on_error=lambda e: {"error": f"Failed to fetch feedback dates: {e}"})
def get_all_feedback_dates():
    query = """
    SELECT DISTINCT date
    FROM feedback_records
    ORDER BY date DESC;
    """
    result = _db.execute_readonly_query(query)
    return [row[0] for row in result]


def get_feedback_by_date(date_str):
    query = """
    SELECT s.name AS section_name, f.feedback
    FROM sections s
    LEFT JOIN feedback f ON s.id = f.section_id AND f.date = :date;
    """
    feedback_rows = _db.execute_readonly_query(query, {"date": date_str})
    return {row[0]: row[1] for row in feedback_rows}


def save_devos_feedback(section_name: str, date_str: str, new_feedback: str, editor_id: int) -> None:
    # Single-query approach: INSERT...SELECT eliminates the TOCTOU gap between
    # the section lookup and the upsert. RETURNING lets us detect a missing section.
    query = """
        INSERT INTO feedback (section_id, date, feedback, last_edited_by, last_edited_at)
        SELECT s.id, :date_str, :new_feedback, :editor_id, CURRENT_TIMESTAMP
        FROM sections s WHERE s.name = :section_name
        ON CONFLICT (section_id, date) DO UPDATE
          SET feedback = EXCLUDED.feedback,
              last_edited_by = EXCLUDED.last_edited_by,
              last_edited_at = EXCLUDED.last_edited_at
        RETURNING section_id;
    """
    rows = _db.execute_query(query, {
        'section_name': section_name,
        'date_str': date_str,
        'new_feedback': new_feedback,
        'editor_id': editor_id
    })
    if not rows:
        raise ValidationError("Section not found")
    clear_group("feedback")
