import logging
from collections import defaultdict
from datetime import date, datetime, timedelta

import backend.bcssm_backend.db_utils as _db
from backend.bcssm_backend.cache_utils import cached_result

logger = logging.getLogger(__name__)

SCHEDULE_START = date(2026, 7, 4)
SCHEDULE_END = SCHEDULE_START + timedelta(days=13)
DUTY_SCHEDULE_CACHE_KEY = 'duties:schedule:14day:2026'


def _user_duty_key(user_name):
    return f'user:duty:{user_name}:{datetime.now().date()}'


@cached_result(_user_duty_key, registry_key='user:duty:{name}:{date}')
def get_user_duty(user_name):
    query = """
    SELECT
        u.name AS user_name,
        COALESCE(s.name, 'Unassigned') AS section,
        u.role,
        COALESCE(dt.name, 'No Team') AS team,
        COALESCE(d.name, 'No Duty') AS duty
    FROM users u
    LEFT JOIN sections s ON u.section_id = s.id
    LEFT JOIN duty_teams dt ON u.duty_team_id = dt.id
    LEFT JOIN duty_schedule ds ON dt.id = ds.duty_team_id
        AND ds.schedule_date = CURRENT_DATE
    LEFT JOIN duties d ON ds.duty_id = d.id
    WHERE u.name = :user_name;
    """
    result = _db.execute_readonly_query(query, {"user_name": user_name})
    if not result:
        return {"error": "User not found or no duty assigned"}
    row = result[0]
    if len(row) < 5:
        logger.error("Unexpected row format in get_user_duty for %s: %s", user_name, row)
        return {"error": "Unexpected data format from database"}
    return {
        "user": row[0],
        "section": row[1],
        "role": row[2],
        "team": row[3],
        "duty": row[4],
    }


def _todays_duties_key(user_name):
    return f'duties:today:{datetime.now().date()}:user{user_name}'


@cached_result(_todays_duties_key, registry_key='duties:today:{date}:{name}', on_error=[])
def get_todays_duties(user_name):
    query = '''
    SELECT
        d.id,
        d.name,
        d.duty_description,
        dt.name AS team_name,
        array_agg(
            jsonb_build_object(
                'name', u.name,
                'week', u.week
            )
            ORDER BY
                CASE u.week
                    WHEN 'Both' THEN 0
                    WHEN 'Week A' THEN 1
                    WHEN 'Week B' THEN 2
                    ELSE 3
                END,
                u.name
        ) FILTER (WHERE u.name IS NOT NULL) AS members,
        COALESCE(bool_or(u.name = :user_name) FILTER (WHERE u.name IS NOT NULL), FALSE) AS is_current_user
    FROM duty_schedule ds
    JOIN duties d ON ds.duty_id = d.id
    JOIN duty_teams dt ON ds.duty_team_id = dt.id
    LEFT JOIN users u ON u.duty_team_id = dt.id
    WHERE ds.schedule_date = CURRENT_DATE
    GROUP BY d.id, d.name, d.duty_description, dt.name, d.display_order
    ORDER BY d.display_order;
    '''
    rows = _db.execute_readonly_query(query, {"user_name": user_name})
    return [
        {
            "id": row[0],
            "name": row[1],
            "duty_description": row[2],
            "team_name": row[3],
            "members": row[4] or [],
            "is_current_user": row[5],
        }
        for row in rows
    ]


def _build_schedule(rows: list) -> list[dict]:
    duty_lookup: dict[date, list] = defaultdict(list)
    duty_order: dict[str, int] = {}
    for row in rows:
        schedule_date, duty_name, duty_description, display_order, team_name, team_members = row
        duty_order[duty_name] = display_order
        duty_lookup[schedule_date].append({
            "duty_name": duty_name,
            "duty_description": duty_description,
            "team_name": team_name,
            "team_members": team_members or [],
        })

    schedule = []
    for i in range(14):
        current_date = SCHEDULE_START + timedelta(days=i)
        schedule.append({
            "date": current_date.strftime("%Y-%m-%d"),
            "day_name": current_date.strftime("%A"),
            "week": "Week A" if i < 7 else "Week B",
            "duties": duty_lookup.get(current_date, []),
        })
    return {"schedule": schedule, "duty_order": duty_order}


@cached_result(DUTY_SCHEDULE_CACHE_KEY, on_error=[])
def get_duty_schedule():
    query = '''
    SELECT
        ds.schedule_date,
        d.name AS duty_name,
        d.duty_description,
        d.display_order,
        dt.name AS team_name,
        array_agg(
            jsonb_build_object(
                'name', u.name,
                'week', u.week
            )
            ORDER BY
                CASE u.week
                    WHEN 'Both' THEN 0
                    WHEN 'Week A' THEN 1
                    WHEN 'Week B' THEN 2
                    ELSE 3
                END,
                u.name
        ) FILTER (WHERE u.name IS NOT NULL) AS team_members
    FROM duty_schedule ds
    JOIN duties d ON ds.duty_id = d.id
    JOIN duty_teams dt ON ds.duty_team_id = dt.id
    LEFT JOIN users u ON u.duty_team_id = dt.id
    WHERE ds.schedule_date BETWEEN :start_date AND :end_date
    GROUP BY ds.schedule_date, d.name, d.duty_description, d.display_order, dt.name, d.id
    ORDER BY ds.schedule_date, d.display_order;
    '''
    rows = _db.execute_readonly_query(query, {
        "start_date": SCHEDULE_START,
        "end_date": SCHEDULE_END,
    })
    return _build_schedule(rows)
