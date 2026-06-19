import logging

import backend.bcssm_backend.db as _db
from backend.bcssm_backend.cache_utils import cached_result

logger = logging.getLogger(__name__)


@cached_result('sections:all:list',
               on_error=lambda e: {"error": f"Failed to fetch sections: {e}"})
def get_all_sections():
    query = """
    SELECT name
    FROM sections
    ORDER BY display_order, name;
    """
    result = _db.execute_readonly_query(query)
    return [row[0] for row in result]


@cached_result('sections:with_users:all_v6',
               on_error=lambda e: {"error": f"Failed to fetch sections with users: {e}"})
def get_all_sections_with_users():
    query = """
    SELECT
        COALESCE(s.name, 'Unassigned') AS section_name,
        COALESCE(s.display_order, 999) AS display_order,
        u.name AS user_name,
        CASE
            WHEN u.role = 'Admin' THEN 'Section Leader'
            ELSE u.role
        END AS display_role,
        u.week
    FROM sections s
    RIGHT JOIN users u ON s.id = u.section_id
    ORDER BY
        COALESCE(s.display_order, 999),
        COALESCE(s.name, 'Unassigned'),
        -- Sort Section Leaders first (by first name), then others by surname
        CASE
            WHEN u.role = 'Admin' OR u.role = 'Section Leader' THEN 0
            ELSE 1
        END,
        CASE
            WHEN u.role = 'Admin' OR u.role = 'Section Leader' THEN u.name
            ELSE CASE
                WHEN POSITION(' ' IN u.name) > 0
                THEN SUBSTRING(u.name FROM POSITION(' ' IN u.name) + 1)
                ELSE u.name
            END
        END,
        u.name;
    """

    rows = _db.execute_readonly_query(query)
    sections_dict = {}
    for row in rows:
        section_name = row[0]
        user_name = row[2]
        display_role = row[3]
        week = row[4]
        if section_name not in sections_dict:
            sections_dict[section_name] = {
                "name": section_name,
                "display_order": row[1],
                "users": [],
                "user_count": 0
            }
        if user_name:
            sections_dict[section_name]["users"].append({
                "name": user_name,
                "role": display_role,
                "week": week
            })
            sections_dict[section_name]["user_count"] += 1
    sections_list = list(sections_dict.values())
    sections_list.sort(key=lambda x: (x["display_order"], x["name"]))
    return sections_list


@cached_result('sections:statistics:summary',
               on_error=lambda e: {"error": f"Failed to fetch section statistics: {e}"})
def get_section_statistics():
    query = """
    SELECT
        COALESCE(s.name, 'Unassigned') AS section_name,
        COALESCE(s.display_order, 999) AS display_order,
        COUNT(u.id) AS total_users,
        COUNT(CASE WHEN u.role IN ('Section Leader', 'Admin') THEN 1 END) AS section_leaders,
        COUNT(CASE WHEN u.role = 'Team Leader' THEN 1 END) AS team_leaders,
        COUNT(CASE WHEN u.role NOT IN ('Section Leader', 'Admin', 'Team Leader') THEN 1 END) AS other_roles
    FROM sections s
    RIGHT JOIN users u ON s.id = u.section_id
    GROUP BY s.id, s.name, s.display_order
    ORDER BY COALESCE(s.display_order, 999), COALESCE(s.name, 'Unassigned');
    """
    rows = _db.execute_readonly_query(query)
    return [
        {
            "section_name": row[0],
            "display_order": row[1],
            "total_users": row[2],
            "section_leaders": row[3],
            "team_leaders": row[4],
            "other_roles": row[5]
        }
        for row in rows
    ]


@cached_result(lambda section_name: f'users:section:{section_name}',
               registry_key='users:section:{name}',
               on_error=lambda e: {"error": f"Failed to fetch users by section: {e}"})
def get_users_by_section(section_name):
    if section_name == "Unassigned":
        query = """
        SELECT u.name,
               CASE
                   WHEN u.role = 'Admin' THEN 'Section Leader'
                   ELSE u.role
               END AS display_role
        FROM users u
        WHERE u.section_id IS NULL
        ORDER BY u.name;
        """
        params = {}
    else:
        query = """
        SELECT u.name,
               CASE
                   WHEN u.role = 'Admin' THEN 'Section Leader'
                   ELSE u.role
               END AS display_role
        FROM users u
        INNER JOIN sections s ON u.section_id = s.id
        WHERE s.name = :section_name
        ORDER BY u.name;
        """
        params = {"section_name": section_name}

    result = _db.execute_readonly_query(query, params)
    return [{"name": row[0], "role": row[1]} for row in result]
