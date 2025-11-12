"""Utility functions for the MCP server."""

import contextvars
import os
from typing import Any

from databricks.sdk import WorkspaceClient

header_store: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "header_store"
)


def get_workspace_client() -> WorkspaceClient:
    """
    Get a WorkspaceClient for server operations.

    Uses LAKEBASE_* environment variables if available, otherwise falls back to default authentication.

    Returns:
        WorkspaceClient: Authenticated workspace client
    """
    # Check for LAKEBASE_* environment variables for service principal auth
    lakebase_client_id = os.getenv("LAKEBASE_CLIENT_ID")
    lakebase_client_secret = os.getenv("LAKEBASE_CLIENT_SECRET")
    lakebase_host = os.getenv("LAKEBASE_HOST")

    if lakebase_client_id and lakebase_client_secret:
        # Use service principal authentication with LAKEBASE credentials
        if lakebase_host:
            return WorkspaceClient(
                host=lakebase_host,
                client_id=lakebase_client_id,
                client_secret=lakebase_client_secret,
            )
        else:
            return WorkspaceClient(
                client_id=lakebase_client_id,
                client_secret=lakebase_client_secret,
            )
    else:
        # Fall back to default authentication
        return WorkspaceClient()


def get_user_authenticated_workspace_client() -> WorkspaceClient:
    """
    Get a WorkspaceClient authenticated as the current user.

    When running in a Databricks App, this uses the user's token from request headers.
    When running locally, it uses the default authentication.

    Returns:
        WorkspaceClient: Authenticated workspace client

    Raises:
        ValueError: If running in Databricks App but token not found in headers
    """
    # Check if running in a Databricks App environment
    is_databricks_app = "DATABRICKS_APP_NAME" in os.environ

    if not is_databricks_app:
        # Running locally, try LAKEBASE credentials first, then default authentication
        lakebase_client_id = os.getenv("LAKEBASE_CLIENT_ID")
        lakebase_client_secret = os.getenv("LAKEBASE_CLIENT_SECRET")
        lakebase_host = os.getenv("LAKEBASE_HOST")

        if lakebase_client_id and lakebase_client_secret:
            if lakebase_host:
                return WorkspaceClient(
                    host=lakebase_host,
                    client_id=lakebase_client_id,
                    client_secret=lakebase_client_secret,
                )
            else:
                return WorkspaceClient(
                    client_id=lakebase_client_id,
                    client_secret=lakebase_client_secret,
                )
        return WorkspaceClient()

    # Running in Databricks App, require user authentication token
    headers: dict[str, Any] = header_store.get({})
    token: str | None = headers.get("x-forwarded-access-token")

    if not token:
        raise ValueError(
            "Authentication token not found in request headers (x-forwarded-access-token). "
            "This is required when running as a Databricks App."
        )

    return WorkspaceClient(token=token, auth_type="pat")
