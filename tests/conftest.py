"""Pytest configuration and fixtures."""

import sys
from pathlib import Path

root_dir = Path(__file__).parents[1]
# Add root directory to path since mcp_state_server is now at top level
sys.path.insert(0, str(root_dir))

import os  # noqa: E402
from collections.abc import Generator  # noqa: E402

import pytest  # noqa: E402
from dotenv import find_dotenv, load_dotenv  # noqa: E402

from mcp_state_server.database.connection import DatabaseConnection  # noqa: E402
from mcp_state_server.database.schema import provision_schema  # noqa: E402

# Load environment variables from .env file, but allow test-specific overrides
# Tests should use local database, so we override PGHOST and related vars after loading
load_dotenv(find_dotenv(), override=False)


@pytest.fixture(scope="session")
def test_db_connection() -> Generator[DatabaseConnection, None, None]:
    """
    Create a database connection for testing.

    Uses TEST_PGHOST, TEST_PGPORT, TEST_PGDATABASE, TEST_PGUSER, TEST_PGPASSWORD
    if available, otherwise falls back to local defaults.
    """
    host = os.getenv("TEST_PGHOST", "localhost")
    port = int(os.getenv("TEST_PGPORT", "5432"))
    database = os.getenv("TEST_PGDATABASE", "test_mcp_state")
    user = os.getenv("TEST_PGUSER", "postgres")
    password = os.getenv("TEST_PGPASSWORD", "postgres")

    try:
        db_conn = DatabaseConnection(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            use_databricks_auth=False,
        )
        # Test connection
        with db_conn.get_connection() as conn:
            conn.cursor().execute("SELECT 1")
        yield db_conn
        db_conn.close()
    except Exception as e:
        pytest.skip(f"Database not available for testing: {e}")


@pytest.fixture(autouse=True)
def reset_db(test_db_connection: DatabaseConnection) -> Generator[None, None, None]:
    """
    Reset database tables before and after each test.

    This fixture runs automatically for all tests that use test_db_connection.
    """
    # Provision schema if needed
    try:
        provision_schema()
    except Exception:
        pass

    # Truncate tables before test
    with test_db_connection.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE messages CASCADE")
        cur.execute("TRUNCATE TABLE conversations CASCADE")
        cur.execute("TRUNCATE TABLE user_preferences CASCADE")
        conn.commit()

    yield

    # Truncate tables after test
    with test_db_connection.get_connection() as conn:
        cur = conn.cursor()
        cur.execute("TRUNCATE TABLE messages CASCADE")
        cur.execute("TRUNCATE TABLE conversations CASCADE")
        cur.execute("TRUNCATE TABLE user_preferences CASCADE")
        conn.commit()
