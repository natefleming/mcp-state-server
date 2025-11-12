"""Database connection management for Databricks Lakehouse Postgres."""

import os
import threading
import uuid
from collections import deque
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from collections.abc import Iterator
from typing import Any

import psycopg2
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.database import DatabaseCredential, DatabaseInstance
from databricks.sdk.service.iam import User
from loguru import logger
from psycopg2.extras import RealDictCursor


class SimpleConnectionPool:
    """Simple thread-safe connection pool for psycopg2."""

    def __init__(
        self,
        minconn: int,
        maxconn: int,
        **conn_params: Any,
    ) -> None:
        """
        Initialize connection pool.

        Args:
            minconn: Minimum number of connections
            maxconn: Maximum number of connections
            **conn_params: Connection parameters for psycopg2.connect()
        """
        self.minconn = minconn
        self.maxconn = maxconn
        self.conn_params = conn_params
        self._pool: deque[Any] = deque()
        self._created = 0
        self._lock = threading.Lock()

    def getconn(self) -> Any:
        """Get a connection from the pool."""
        with self._lock:
            if self._pool:
                return self._pool.popleft()

            if self._created < self.maxconn:
                conn = psycopg2.connect(**self.conn_params)
                self._created += 1
                return conn

            # Wait for a connection to become available
            while not self._pool:
                self._lock.release()
                import time

                time.sleep(0.1)
                self._lock.acquire()

            return self._pool.popleft()

    def putconn(self, conn: Any) -> None:
        """Return a connection to the pool."""
        with self._lock:
            if conn.closed:
                self._created -= 1
            else:
                self._pool.append(conn)

    def closeall(self) -> None:
        """Close all connections in the pool."""
        with self._lock:
            while self._pool:
                conn = self._pool.popleft()
                try:
                    conn.close()
                except Exception:
                    pass
            self._created = 0


class DatabaseConnection:
    """Manages database connections to Databricks Lakehouse Postgres."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
        password: str | None = None,
        instance_name: str | None = None,
        use_databricks_auth: bool = True,
        min_connections: int = 1,
        max_connections: int = 10,
    ) -> None:
        """
        Initialize database connection pool.

        Args:
            host: Database host (optional if using Databricks SDK)
            port: Database port (optional if using Databricks SDK)
            database: Database name
            user: Database user (optional if using Databricks SDK)
            password: Database password (optional if using Databricks SDK)
            instance_name: Databricks Lakehouse Postgres instance name
            use_databricks_auth: Whether to use Databricks SDK for authentication
            min_connections: Minimum pool connections
            max_connections: Maximum pool connections
        """
        self.use_databricks_auth = use_databricks_auth
        self.instance_name = (
            instance_name
            or os.getenv("LAKEBASE_INSTANCE_NAME")
            or os.getenv("DATABRICKS_POSTGRES_INSTANCE_NAME")
        )

        if use_databricks_auth:
            # Use Databricks SDK for authentication
            # Check for LAKEBASE_* environment variables for service principal auth
            lakebase_client_id = os.getenv("LAKEBASE_CLIENT_ID")
            lakebase_client_secret = os.getenv("LAKEBASE_CLIENT_SECRET")
            lakebase_host = os.getenv("LAKEBASE_HOST")

            if lakebase_client_id and lakebase_client_secret:
                # Use service principal authentication with LAKEBASE credentials
                logger.info("Using LAKEBASE service principal authentication")
                if lakebase_host:
                    self._workspace_client = WorkspaceClient(
                        host=lakebase_host,
                        client_id=lakebase_client_id,
                        client_secret=lakebase_client_secret,
                    )
                else:
                    self._workspace_client = WorkspaceClient(
                        client_id=lakebase_client_id,
                        client_secret=lakebase_client_secret,
                    )
            else:
                # Fall back to default authentication
                logger.info("Using default WorkspaceClient authentication")
                self._workspace_client = WorkspaceClient()

            # Log current user from workspace client
            try:
                current_user: User | None = self._workspace_client.current_user.me()
                logger.info(f"WorkspaceClient created. Current user: {current_user}")
                # Log all available attributes for debugging
                if current_user and isinstance(current_user, User):
                    user_attrs = {
                        attr: getattr(current_user, attr, None)
                        for attr in dir(current_user)
                        if not attr.startswith("_")
                        and not callable(getattr(current_user, attr, None))
                    }
                    logger.debug(f"Current user attributes: {user_attrs}")
            except Exception as e:
                logger.warning(
                    f"Could not retrieve current user from WorkspaceClient: {e}"
                )

            self._token_expires_at: datetime | None = None
            self._database_instance: DatabaseInstance | None = None
            self._get_connection_details_from_sdk(host, port, database, user)
        else:
            # Use direct connection parameters with standard PostgreSQL env vars
            self.host = host or os.getenv("PGHOST", "localhost")
            self.port = port or int(os.getenv("PGPORT", "5432"))
            self.database = database or os.getenv("PGDATABASE", "databricks_postgres")
            self.user = user or os.getenv("PGUSER", "postgres")
            self.password = password or os.getenv("PGPASSWORD", "")
            self._workspace_client = None

        self.min_connections = min_connections
        self.max_connections = max_connections
        self._connection_pool: SimpleConnectionPool | None = None
        self._initialize_pool(min_connections, max_connections)

    def _get_connection_details_from_sdk(
        self,
        host: str | None = None,
        port: int | None = None,
        database: str | None = None,
        user: str | None = None,
    ) -> None:
        """
        Get connection details from Databricks SDK database API.

        Args:
            host: Optional host override
            port: Optional port override
            database: Optional database override
            user: Optional user override
        """
        try:
            # Get database instance
            if self.instance_name:
                # Get specific instance by name
                self._database_instance = (
                    self._workspace_client.database.get_database_instance(
                        self.instance_name
                    )
                )
                logger.info(f"Retrieved database instance: {self.instance_name}")
            else:
                # Try to find instance from environment or list available instances
                instance_name_env = os.getenv("LAKEBASE_INSTANCE_NAME") or os.getenv(
                    "DATABRICKS_POSTGRES_INSTANCE_NAME"
                )
                if instance_name_env:
                    self._database_instance = (
                        self._workspace_client.database.get_database_instance(
                            instance_name_env
                        )
                    )
                    self.instance_name = instance_name_env
                    logger.info(
                        f"Retrieved database instance from env: {instance_name_env}"
                    )
                else:
                    # List instances and use the first available one
                    instances = list(
                        self._workspace_client.database.list_database_instances()
                    )
                    if not instances:
                        raise ValueError(
                            "No database instances found. Set LAKEBASE_INSTANCE_NAME or DATABRICKS_POSTGRES_INSTANCE_NAME "
                            "environment variable or ensure you have access to a database instance."
                        )
                    # Find first available instance
                    available_instance = next(
                        (inst for inst in instances if inst.state.value == "AVAILABLE"),
                        instances[0],
                    )
                    self._database_instance = available_instance
                    self.instance_name = available_instance.name
                    logger.info(
                        f"Using first available database instance: {self.instance_name}"
                    )

            # Check instance state
            if self._database_instance.state.value != "AVAILABLE":
                raise ValueError(
                    f"Database instance {self.instance_name} is not available. "
                    f"Current state: {self._database_instance.state.value}"
                )

            # Get connection details from instance
            # Use read_write_dns as host (or read_only_dns for read-only if needed)
            instance_host = self._database_instance.read_write_dns
            if not instance_host:
                raise ValueError(
                    f"Database instance {self.instance_name} does not have a connection DNS configured"
                )

            # Extract host and port from DNS or use provided values
            if host:
                self.host = host
            else:
                self.host = instance_host

            # Port defaults to 5432 for PostgreSQL
            self.port = port or int(os.getenv("PGPORT", "5432"))

            # Database name
            self.database = database or os.getenv("PGDATABASE", "databricks_postgres")

            # User - use Databricks identity (current user) or environment variable
            # According to Databricks docs: https://docs.databricks.com/aws/en/oltp/instances/authentication
            # The user should be the Databricks identity (username) for OAuth token authentication
            if user:
                self.user = user
            else:
                # Try to get current user from Databricks SDK
                try:
                    current_user: User | None = self._workspace_client.current_user.me()
                    if (
                        current_user
                        and isinstance(current_user, User)
                        and current_user.user_name
                    ):
                        self.user = current_user.user_name
                        logger.debug(f"Using Databricks identity: {self.user}")
                    else:
                        # Fallback to environment variable
                        self.user = os.getenv("PGUSER")
                except Exception as e:
                    logger.warning(
                        f"Could not get current user from Databricks SDK: {e}"
                    )
                    # Fallback to environment variable
                    self.user = os.getenv("PGUSER")

            if not self.user:
                raise ValueError(
                    "Database user must be set. Set PGUSER environment variable "
                    "or ensure Databricks SDK is configured with a valid identity."
                )

            # Generate database credential
            self._generate_database_credential()

            logger.info(
                f"Retrieved connection details from Databricks SDK: {self.host}:{self.port}/{self.database} "
                f"(instance: {self.instance_name})"
            )
        except Exception as e:
            logger.error(f"Failed to get connection details from Databricks SDK: {e}")
            raise

    def _generate_database_credential(self) -> None:
        """
        Generate database credential using the database API.

        Follows Databricks documentation:
        https://docs.databricks.com/aws/en/oltp/instances/authentication?language=Python+SDK

        OAuth tokens expire after one hour. This method generates a new token
        and tracks its expiration time for automatic refresh.
        """
        if not self.instance_name:
            raise ValueError(
                "Instance name is required to generate database credential"
            )

        try:
            # Generate OAuth token following Databricks SDK pattern
            # See: https://docs.databricks.com/aws/en/oltp/instances/authentication?language=Python+SDK
            credential: DatabaseCredential = (
                self._workspace_client.database.generate_database_credential(
                    request_id=str(uuid.uuid4()), instance_names=[self.instance_name]
                )
            )

            # Use token as password
            self.password = credential.token

            # Parse expiration time
            if credential.expiration_time:
                # expiration_time is ISO format string (e.g., '2025-11-11T18:57:26Z')
                expiration_str = credential.expiration_time
                if expiration_str.endswith("Z"):
                    expiration_str = expiration_str.replace("Z", "+00:00")
                try:
                    self._token_expires_at = datetime.fromisoformat(expiration_str)
                except ValueError:
                    # Fallback: try parsing without timezone
                    self._token_expires_at = datetime.fromisoformat(
                        credential.expiration_time.replace("Z", "")
                    ).replace(tzinfo=None)
                    # Assume UTC if no timezone info
                    self._token_expires_at = self._token_expires_at.replace(tzinfo=UTC)
            else:
                # Default to 1 hour if not specified
                self._token_expires_at = datetime.now(UTC) + timedelta(hours=1)

            logger.debug(
                f"Generated database credential for {self.instance_name}, "
                f"expires at {self._token_expires_at}"
            )
        except Exception as e:
            logger.error(f"Failed to generate database credential: {e}")
            raise

    def _refresh_token_if_needed(self) -> None:
        """
        Refresh database credential token if it's expired or about to expire.

        According to Databricks docs, OAuth tokens expire after one hour.
        We refresh tokens 5 minutes before expiration to ensure continuous operation.
        See: https://docs.databricks.com/aws/en/oltp/instances/authentication?language=Python+SDK
        """
        if not self.use_databricks_auth or not self._workspace_client:
            return

        # Compare timezone-aware datetimes
        # Rotate tokens before hourly expiration (refresh 5 minutes early)
        now = datetime.now(UTC)
        if self._token_expires_at is None or now >= self._token_expires_at - timedelta(
            minutes=5
        ):
            logger.info(
                f"Refreshing Databricks database credential for {self.instance_name} "
                f"(current token expires at {self._token_expires_at})"
            )
            self._generate_database_credential()

            # Reinitialize pool with new token
            # Close existing connections as they may fail with expired tokens
            if self._connection_pool:
                self._connection_pool.closeall()
            self._initialize_pool(self.min_connections, self.max_connections)

    def _initialize_pool(self, min_connections: int, max_connections: int) -> None:
        """Initialize the connection pool."""
        try:
            # Refresh token if using Databricks auth
            if self.use_databricks_auth:
                self._refresh_token_if_needed()

            # Connection parameters
            conn_params = {
                "host": self.host,
                "port": self.port,
                "database": self.database,
                "user": self.user,
                "password": self.password,
                "cursor_factory": RealDictCursor,
            }

            # Add SSL for Databricks Lakehouse Postgres
            # According to Databricks docs, token-based authentication requires SSL connections
            # See: https://docs.databricks.com/aws/en/oltp/instances/authentication?language=Python+SDK
            if self.use_databricks_auth:
                conn_params["sslmode"] = "require"

            self._connection_pool = SimpleConnectionPool(
                min_connections, max_connections, **conn_params
            )
            logger.info(
                f"Database connection pool initialized: {self.host}:{self.port}/{self.database}"
            )
        except Exception as e:
            logger.error(f"Failed to initialize database connection pool: {e}")
            raise

    @contextmanager
    def get_connection(self) -> Iterator[Any]:
        """
        Get a database connection from the pool.

        Yields:
            psycopg2 connection object

        Raises:
            Exception: If connection cannot be obtained
        """
        if self._connection_pool is None:
            raise RuntimeError("Database connection pool not initialized")

        # Refresh token if needed before getting connection
        if self.use_databricks_auth:
            self._refresh_token_if_needed()

        conn = self._connection_pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database transaction error: {e}")
            raise
        finally:
            self._connection_pool.putconn(conn)

    def execute_query(
        self,
        query: str,
        params: tuple | None = None,
        fetch: bool = True,
    ) -> list[dict[str, Any]] | None:
        """
        Execute a query and return results.

        Args:
            query: SQL query string
            params: Query parameters
            fetch: Whether to fetch results

        Returns:
            List of result dictionaries or None
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.execute(query, params)
                if fetch:
                    return cur.fetchall()
                return None
            finally:
                cur.close()

    def execute_many(
        self,
        query: str,
        params_list: list[tuple],
    ) -> None:
        """
        Execute a query multiple times with different parameters.

        Args:
            query: SQL query string
            params_list: List of parameter tuples
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            try:
                cur.executemany(query, params_list)
            finally:
                cur.close()

    def get_instance_info(self) -> dict[str, Any] | None:
        """
        Get information about the database instance.

        Returns:
            Dictionary with instance information or None if not using Databricks auth
        """
        if not self.use_databricks_auth or not self._database_instance:
            return None

        return {
            "name": self._database_instance.name,
            "uid": self._database_instance.uid,
            "state": self._database_instance.state.value,
            "read_write_dns": self._database_instance.read_write_dns,
            "read_only_dns": self._database_instance.read_only_dns,
            "capacity": (
                getattr(self._database_instance.capacity, "value", None)
                if self._database_instance.capacity
                else None
            ),
            "pg_version": (
                getattr(self._database_instance.pg_version, "value", None)
                if self._database_instance.pg_version
                else None
            ),
            "creation_time": self._database_instance.creation_time,
        }

    def close(self) -> None:
        """Close all connections in the pool."""
        if self._connection_pool:
            self._connection_pool.closeall()
            logger.info("Database connection pool closed")


# Global database connection instance
_db_connection: DatabaseConnection | None = None


def get_db_connection() -> DatabaseConnection:
    """
    Get the global database connection instance.

    Returns:
        DatabaseConnection instance

    Raises:
        RuntimeError: If connection is not initialized
    """
    global _db_connection
    if _db_connection is None:
        _db_connection = DatabaseConnection()
    return _db_connection


def initialize_db_connection(
    host: str | None = None,
    port: int | None = None,
    database: str | None = None,
    user: str | None = None,
    password: str | None = None,
    instance_name: str | None = None,
    use_databricks_auth: bool = True,
) -> DatabaseConnection:
    """
    Initialize the global database connection.

    Args:
        host: Database host (optional if using Databricks SDK)
        port: Database port (optional if using Databricks SDK)
        database: Database name
        user: Database user (optional if using Databricks SDK)
        password: Database password (optional if using Databricks SDK)
        instance_name: Databricks Lakehouse Postgres instance name
        use_databricks_auth: Whether to use Databricks SDK for authentication

    Returns:
        DatabaseConnection instance
    """
    global _db_connection
    _db_connection = DatabaseConnection(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        instance_name=instance_name,
        use_databricks_auth=use_databricks_auth,
    )
    return _db_connection
