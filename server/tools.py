"""
Tools module for the MCP server.

This module defines all the tools (functions) that the MCP server exposes to clients.
Tools are the core functionality of an MCP server - they are callable functions that
AI assistants and other clients can invoke to perform specific actions.

Each tool should:
- Have a clear, descriptive name
- Include comprehensive docstrings (used by AI to understand when to call the tool)
- Return structured data (typically dict or list)
- Handle errors gracefully
"""

from typing import Any

from fastmcp import FastMCP
from loguru import logger

from mcp_state_server.database.connection import get_db_connection
from mcp_state_server.database.repository import ConversationRepository, UserPreferencesRepository
from mcp_state_server.models.conversation import Conversation, ConversationMessage
from mcp_state_server.models.user_preferences import UserPreferences

from . import utils


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
            w = utils.get_user_authenticated_workspace_client()
            user = w.current_user.me()
            return {
                "display_name": user.display_name,
                "user_name": user.user_name,
                "active": user.active,
            }
        except Exception as e:
            logger.error(f"Failed to get current user: {e}")
            return {"error": str(e), "message": "Failed to retrieve user information"}

    # Conversation management tools
    @mcp_server.tool()
    async def save_conversation(
        conversation_id: str,
        user_id: str,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Save or update a conversation. Creates a new conversation if it doesn't exist, or updates existing one.

        Args:
            conversation_id: Unique identifier for the conversation
            user_id: User ID who owns the conversation
            title: Optional conversation title
            metadata: Optional metadata dictionary

        Returns:
            dict: Success message with conversation ID
        """
        try:
            db = get_db_connection()
            repo = ConversationRepository(db)

            conversation = Conversation(
                id=conversation_id,
                user_id=user_id,
                title=title,
                metadata=metadata or {},
            )

            saved = repo.save_conversation(conversation)
            logger.info(f"Saved conversation {conversation_id} for user {user_id}")

            return {"success": True, "conversation_id": saved.id, "message": f"Conversation {saved.id} saved successfully"}
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool()
    async def get_conversation(
        conversation_id: str,
        include_messages: bool = True,
    ) -> dict[str, Any]:
        """
        Retrieve a conversation by ID, optionally including all messages.

        Args:
            conversation_id: Conversation ID to retrieve
            include_messages: Whether to include messages in the response

        Returns:
            dict: Conversation data as dictionary
        """
        try:
            db = get_db_connection()
            repo = ConversationRepository(db)

            conversation = repo.get_conversation(conversation_id, include_messages)

            if not conversation:
                return {"success": False, "error": f"Conversation {conversation_id} not found"}

            return {"success": True, "conversation": conversation.model_dump()}
        except Exception as e:
            logger.error(f"Error getting conversation: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool()
    async def list_conversations(
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """
        List conversations for a user with pagination support.

        Args:
            user_id: User ID to list conversations for
            limit: Maximum number of conversations to return
            offset: Offset for pagination

        Returns:
            dict: List of conversations as dictionary
        """
        try:
            db = get_db_connection()
            repo = ConversationRepository(db)

            conversations = repo.list_conversations(user_id, limit, offset)

            return {
                "success": True,
                "conversations": [conv.model_dump() for conv in conversations],
                "count": len(conversations),
            }
        except Exception as e:
            logger.error(f"Error listing conversations: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool()
    async def delete_conversation(conversation_id: str) -> dict[str, Any]:
        """
        Delete a conversation and all its messages.

        Args:
            conversation_id: Conversation ID to delete

        Returns:
            dict: Success message
        """
        try:
            db = get_db_connection()
            repo = ConversationRepository(db)

            deleted = repo.delete_conversation(conversation_id)

            if deleted:
                logger.info(f"Deleted conversation {conversation_id}")
                return {"success": True, "message": f"Conversation {conversation_id} deleted successfully"}
            else:
                return {"success": False, "error": f"Conversation {conversation_id} not found"}
        except Exception as e:
            logger.error(f"Error deleting conversation: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool()
    async def save_message(
        conversation_id: str,
        role: str,
        content: str,
        tool_calls: list[dict[str, Any]] | None = None,
        tool_call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Save a message to a conversation.

        Args:
            conversation_id: Conversation ID
            role: Message role (user, assistant, system, tool)
            content: Message content
            tool_calls: Optional tool calls if this is an assistant message
            tool_call_id: Tool call ID if this is a tool message
            metadata: Optional metadata dictionary

        Returns:
            dict: Success message with message ID
        """
        try:
            db = get_db_connection()
            repo = ConversationRepository(db)

            message = ConversationMessage(
                conversation_id=conversation_id,
                role=role,
                content=content,
                tool_calls=tool_calls,
                tool_call_id=tool_call_id,
                metadata=metadata or {},
            )

            saved = repo.save_message(message)
            logger.info(f"Saved message {saved.id} to conversation {conversation_id}")

            return {"success": True, "message_id": saved.id, "message": f"Message saved with ID: {saved.id}"}
        except Exception as e:
            logger.error(f"Error saving message: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool()
    async def get_messages(conversation_id: str) -> dict[str, Any]:
        """
        Get all messages for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            dict: List of messages as dictionary
        """
        try:
            db = get_db_connection()
            repo = ConversationRepository(db)

            messages = repo.get_messages(conversation_id)

            return {
                "success": True,
                "messages": [msg.model_dump() for msg in messages],
                "count": len(messages),
            }
        except Exception as e:
            logger.error(f"Error getting messages: {e}")
            return {"success": False, "error": str(e)}

    @mcp_server.tool()
    async def delete_message(message_id: int) -> dict[str, Any]:
        """
        Delete a message by ID.

        Args:
            message_id: Message ID to delete

        Returns:
            dict: Success message
        """
        try:
            db = get_db_connection()
            repo = ConversationRepository(db)

            deleted = repo.delete_message(message_id)

            if deleted:
                logger.info(f"Deleted message {message_id}")
                return {"success": True, "message": f"Message {message_id} deleted successfully"}
            else:
                return {"success": False, "error": f"Message {message_id} not found"}
        except Exception as e:
            logger.error(f"Error deleting message: {e}")
            return {"success": False, "error": str(e)}

    # User preferences tools
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
                return {"success": False, "error": f"Preference {preference_key} not found for user {user_id}"}

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
                return {"success": True, "message": f"Preference {preference_key} deleted successfully"}
            else:
                return {"success": False, "error": f"Preference {preference_key} not found for user {user_id}"}
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

            return {"success": True, "count": count, "message": f"Deleted {count} preferences for user {user_id}"}
        except Exception as e:
            logger.error(f"Error deleting all preferences: {e}")
            return {"success": False, "error": str(e)}

