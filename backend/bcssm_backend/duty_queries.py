import logging
from collections import defaultdict
from datetime import datetime, timedelta
from functools import lru_cache

import backend.bcssm_backend.db as _db
from backend.bcssm_backend.cache_utils import cached_result

logger = logging.getLogger(__name__)

CYCLE_ANCHOR = datetime(2026, 7, 4)
DUTY_SCHEDULE_CACHE_KEY = 'duties:schedule:14day:anchor'


@lru_cache(maxsize=2)
def _cycle_week_for_date(target_date, anchor=None):
    if anchor is None:
        anchor = CYCLE_ANCHOR.date()
    days_since_cycle_start = (target_date - anchor).days
    return (days_since_cycle_start // 7) % 2


def get_current_cycle_week():
    return _cycle_week_for_date(datetime.now().date())


def _user_duty_key(user_name):
    return f'user:duty:{user_name}:{datetime.now().date()}'


@cached_result(_user_duty_key, registry_key='user:duty:{name}:{date}')
def get_user_duty(user_name):
    current_day = (datetime.now().weekday() + 1) % 7
    current_cycle = get_current_cycle_week()
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
        AND ds.day = :day
        AND ds.cycle_week = :cycle_week
    LEFT JOIN duties d ON ds.duty_id = d.id
    WHERE u.name = :user_name;
    """
    result = _db.execute_readonly_query(query, {
        "user_name": user_name,
        "day": current_day,
        "cycle_week": current_cycle
    })
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
    day = (datetime.now().weekday() + 1) % 7
    cycle = get_current_cycle_week()
    return f'duties:today:day{day}:cycle{cycle}:user{user_name}'


@cached_result(_todays_duties_key, registry_key='duties:today:{day}:{cycle}:{name}', on_error=[])
def get_todays_duties(user_name):
    current_day = (datetime.now().weekday() + 1) % 7
    current_cycle = get_current_cycle_week()
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
        ) AS members,
        bool_or(u.name = :user_name) AS is_current_user
    FROM duty_schedule ds
    JOIN duties d ON ds.duty_id = d.id
    JOIN duty_teams dt ON ds.duty_team_id = dt.id
    LEFT JOIN users u ON u.duty_team_id = dt.id
    WHERE ds.day = :day
        AND ds.cycle_week = :cycle_week
    GROUP BY d.id, d.name, d.duty_description, dt.name
    ORDER BY d.name;
    '''
    rows = _db.execute_readonly_query(query, {
        "day": current_day,
        "user_name": user_name,
        "cycle_week": current_cycle
    })
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


def _build_schedule(start_date: datetime, rows: list) -> list[dict]:
    """Build a 14-day schedule from a fixed anchor date and raw DB rows."""
    date_to_info = {}
    for i in range(14):
        current_date = start_date + timedelta(days=i)
        db_day = (current_date.weekday() + 1) % 7
        cycle_week = _cycle_week_for_date(current_date.date(), anchor=start_date.date())
        date_to_info[current_date.date()] = {
            "day": db_day,
            "cycle_week": cycle_week,
            "week_name": "Week A" if cycle_week == 0 else "Week B",
        }

    duty_lookup = defaultdict(list)
    for row in rows:
        day, cycle_week, duty_name, duty_description, team_name, team_members = row
        duty_lookup[(day, cycle_week)].append({
            "duty_name": duty_name,
            "duty_description": duty_description,
            "team_name": team_name,
            "team_members": team_members or []
        })

    schedule = []
    for dt in sorted(date_to_info.keys()):
        info = date_to_info[dt]
        schedule.append({
            "date": dt.strftime("%Y-%m-%d"),
            "day_name": dt.strftime("%A"),
            "week": info["week_name"],
            "duties": duty_lookup.get((info["day"], info["cycle_week"]), []),
        })
    return schedule


@cached_result(DUTY_SCHEDULE_CACHE_KEY, on_error=[])
def get_duty_schedule():
    combinations = [
        (
            ((CYCLE_ANCHOR + timedelta(days=i)).weekday() + 1) % 7,
            _cycle_week_for_date((CYCLE_ANCHOR + timedelta(days=i)).date()),
        )
        for i in range(14)
    ]
    days = list({c[0] for c in combinations})
    cycles = list({c[1] for c in combinations})

    query = '''
    SELECT
        ds.day,
        ds.cycle_week,
        d.name AS duty_name,
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
        ) AS team_members
    FROM duty_schedule ds
    JOIN duties d ON ds.duty_id = d.id
    JOIN duty_teams dt ON ds.duty_team_id = dt.id
    LEFT JOIN users u ON u.duty_team_id = dt.id
    WHERE ds.day = ANY(:days)
        AND ds.cycle_week = ANY(:cycles)
    GROUP BY ds.day, ds.cycle_week, d.name, d.duty_description, dt.name, d.id
    ORDER BY ds.day, d.name;
    '''

    rows = _db.execute_readonly_query(query, {"days": days, "cycles": cycles})
    return _build_schedule(CYCLE_ANCHOR, rows)
