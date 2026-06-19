import logging

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from backend.globals import db
from backend.bcssm_backend.exceptions import DatabaseError

logger = logging.getLogger(__name__)


def execute_readonly_query(query, params=None, silent=False):
    """
    Execute a read-only SQL query using a dedicated engine connection, avoiding session overhead.
    Pass silent=True for auth/sensitive queries to suppress param and row logging.
    Returns: list of result rows
    """
    try:
        with db.engine.connect() as conn:
            if not silent:
                logger.info("Executing read-only query: %s with params: %s", query, params)
            result = conn.execute(text(query), params)
            rows = result.fetchall()
            if not silent:
                logger.info("Rows fetched: %s", rows)
            return rows
    except SQLAlchemyError as e:
        logger.error("Read-only query failed. Query: %s, Error: %s", query, e)
        raise DatabaseError("Database error") from e


def execute_query(query, params=None, silent=False):
    try:
        with db.session.begin():
            if not silent:
                logger.info("Executing query: %s with params: %s", query, params)
            result = db.session.execute(text(query), params)
            if result.returns_rows:
                rows = result.fetchall()
                if not silent:
                    logger.info("Raw rows fetched: %s", rows)
                return rows
            if not silent:
                logger.info("Query executed successfully with no rows returned.")
            return None

    except SQLAlchemyError as e:
        logger.error(
            "Query failed. Query: %s, Params: %s, Error: %s",
            query,
            "<redacted>" if silent else params,
            e,
        )
        raise DatabaseError("Database error") from e
