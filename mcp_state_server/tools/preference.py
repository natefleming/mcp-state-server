"""MCP tools for user preferences management."""

from typing import Any

from fastmcp import FastMCP
from loguru import logger

from mcp_state_server.database.connection import get_db_connection
from mcp_state_server.database.repository import UserPreferencesRepository
from mcp_state_server.models.user_preferences import UserPreferences


def load_preference_tools(mcp_server: FastMCP) -> None:
    """
    Register user preference management tools with the MCP server.

    Args:
        mcp_server: The FastMCP server instance to register tools with.
    """

    @mcp_server.tool()
    async def save_preference(
        user_id: str,
        preference_key: str,
        preference_value: Any,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Save or update a user preference. Creates a new preference if it doesn't exist, or updates existing one.

        Args:
            user_id: User ID
            preference_key: Preference key (e.g., 'theme', 'language', 'notifications')
            preference_value: Preference value (can be string, number, boolean, object, or array)
            metadata: Optional metadata dictionary

        Returns:
            dict: Saved preference as dictionary
        """
        try:
            db = get_db_connection()
            repo = UserPreferencesRepository(db)

            preference = UserPreferences(
                user_id=user_id,
                preference_key=preference_key,
                preference_value=preference_value,
                metadata=metadata or {},
            )

            saved = repo.save_preference(preference)
            logger.info(f"Saved preference {preference_key} for user {user_id}")

            return {"success": True, "preference": saved.model_dump()}
        except Exception as e:
            logger.error(f"Error saving preference: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool()
    async def get_preference(user_id: str, preference_key: str) -> dict[str, Any]:
        """
        Get a specific user preference by key.

        Args:
            user_id: User ID
            preference_key: Preference key to retrieve

        Returns:
            dict: Preference data as dictionary
        """
        try:
            db = get_db_connection()
            repo = UserPreferencesRepository(db)

            preference = repo.get_preference(user_id, preference_key)

            if not preference:
                return {
                    "success": False,
                    "error": f"Preference {preference_key} not found for user {user_id}",
                }

            return {"success": True, "preference": preference.model_dump()}
        except Exception as e:
            logger.error(f"Error getting preference: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool()
    async def get_all_preferences(user_id: str) -> dict[str, Any]:
        """
        Get all preferences for a user.

        Args:
            user_id: User ID

        Returns:
            dict: All preferences as dictionary
        """
        try:
            db = get_db_connection()
            repo = UserPreferencesRepository(db)

            preferences = repo.get_all_preferences(user_id)

            return {
                "success": True,
                "preferences": preferences,
                "count": len(preferences),
            }
        except Exception as e:
            logger.error(f"Error getting all preferences: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool()
    async def delete_preference(user_id: str, preference_key: str) -> dict[str, Any]:
        """
        Delete a specific user preference.

        Args:
            user_id: User ID
            preference_key: Preference key to delete

        Returns:
            dict: Success message
        """
        try:
            db = get_db_connection()
            repo = UserPreferencesRepository(db)

            deleted = repo.delete_preference(user_id, preference_key)

            if deleted:
                logger.info(f"Deleted preference {preference_key} for user {user_id}")
                return {
                    "success": True,
                    "message": f"Preference {preference_key} deleted successfully",
                }
            else:
                return {
                    "success": False,
                    "error": f"Preference {preference_key} not found for user {user_id}",
                }
        except Exception as e:
            logger.error(f"Error deleting preference: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool()
    async def delete_all_preferences(user_id: str) -> dict[str, Any]:
        """
        Delete all preferences for a user.

        Args:
            user_id: User ID

        Returns:
            dict: Success message with count
        """
        try:
            db = get_db_connection()
            repo = UserPreferencesRepository(db)

            count = repo.delete_all_preferences(user_id)
            logger.info(f"Deleted {count} preferences for user {user_id}")

            return {
                "success": True,
                "count": count,
                "message": f"Deleted {count} preferences for user {user_id}",
            }
        except Exception as e:
            logger.error(f"Error deleting all preferences: {e}")
            return {"success": False, "error": str(e)}
