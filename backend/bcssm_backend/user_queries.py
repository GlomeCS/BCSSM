import logging

import backend.bcssm_backend.db_utils as _db
from backend.bcssm_backend.cache_utils import cached_result
from backend.bcssm_backend.exceptions import DatabaseError

logger = logging.getLogger(__name__)


@cached_result('users:all:list', on_error=[])
def get_all_users():
    query = """
    SELECT
        u.name,
        COALESCE(s.name, 'Unassigned') AS section,
        u.role,
        COALESCE(dt.name, 'No Team') AS team
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    LEFT JOIN duty_teams dt ON u.duty_team_id = dt.id
    ORDER BY
        CASE
            WHEN POSITION(' ' IN u.name) > 0
            THEN SUBSTRING(u.name FROM POSITION(' ' IN u.name) + 1)
            ELSE u.name
        END,
        u.name;
    """
    rows = _db.execute_readonly_query(query)
    return [row[0] for row in rows]


def _fetch_user_info(where_clause, params):
    # where_clause must be a hard-coded SQL fragment (e.g. "u.name = :user_name");
    # all user input goes through params so execute_readonly_query keeps it parameterized.
    query = (
        "SELECT u.name, u.role, s.name AS section_name "
        "FROM users u "
        "LEFT JOIN sections s ON u.section_id = s.id "
        f"WHERE {where_clause};"
    )
    rows = _db.execute_readonly_query(query, params)
    if rows:
        return {"name": rows[0][0], "role": rows[0][1], "section": rows[0][2]}
    return None


def get_user_info(user_name):
    return _fetch_user_info("u.name = :user_name", {"user_name": user_name})


def get_user_id_by_name(user_name):
    """Return the DB id for user_name, or None if not found."""
    try:
        rows = _db.execute_readonly_query(
            "SELECT id FROM users WHERE name = :user_name;",
            {"user_name": user_name},
            silent=True,
        )
        return rows[0][0] if rows else None
    except DatabaseError as e:
        logger.warning("Could not resolve user_id for %s: %s", user_name, e)
        return None


def get_user_info_by_id(user_id):
    return _fetch_user_info("u.id = :user_id", {"user_id": user_id})
