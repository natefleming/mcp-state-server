"""Tools package for MCP State Server."""

from typing import Any

from fastmcp import FastMCP
from loguru import logger

from mcp_state_server.database.connection import get_db_connection

from .conversation import load_conversation_tools
from .preference import load_preference_tools


def load_tools(mcp_server: FastMCP) -> None:
    """
    Register all MCP tools with the server.

    This function is called during server initialization to register all available
    tools with the MCP server instance. Tools are registered using the @mcp_server.tool
    decorator, which makes them available to clients via the MCP protocol.

    Args:
        mcp_server: The FastMCP server instance to register tools with. This is the
                   main server object that handles tool registration and routing.
    """
    # Register health and user tools
    @mcp_server.tool()
    async def health() -> dict[str, Any]:
        """
        Check the health of the MCP server and database connection.

        This is a simple diagnostic tool that confirms the server is running properly.
        It's useful for:
        - Monitoring and health checks
        - Testing the MCP connection
        - Verifying the server is responsive

        Returns:
            dict: A dictionary containing:
                - status (str): The health status ("healthy" if operational)
                - message (str): A human-readable status message
        """
        try:
            # Test database connection
            db = get_db_connection()
            with db.get_connection() as conn:
                conn.cursor().execute("SELECT 1")
            return {
                "status": "healthy",
                "message": "MCP State Server is healthy and connected to database.",
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "message": f"Server is running but database connection failed: {str(e)}",
            }

    @mcp_server.tool()
    async def get_current_user() -> dict[str, Any]:
        """
        Get information about the current authenticated user.

        This tool retrieves details about the user who is currently authenticated
        with the MCP server. When deployed as a Databricks App, this returns
        information about the end user making the request. When running locally,
        it returns information about the developer's Databricks identity.

        Useful for:
        - Personalizing responses based on the user
        - Authorization checks
        - Audit logging
        - User-specific operations

        Returns:
            dict: A dictionary containing:
                - display_name (str): The user's display name
                - user_name (str): The user's username/email
                - active (bool): Whether the user account is active
        """
        try:
            from server.utils import get_user_authenticated_workspace_client

            w = get_user_authenticated_workspace_client()
            user = w.current_user.me()
            return {
                "display_name": user.display_name,
                "user_name": user.user_name,
                "active": user.active,
            }
        except Exception as e:
            logger.error(f"Failed to get current user: {e}")
            return {"error": str(e), "message": "Failed to retrieve user information"}

    # Load conversation and preference tools
    load_conversation_tools(mcp_server)
    load_preference_tools(mcp_server)

__all__ = [
    "load_tools",
]
