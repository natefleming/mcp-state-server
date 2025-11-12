"""MCP tools for conversation management."""

from typing import Any

from fastmcp import FastMCP
from loguru import logger

from mcp_state_server.database.connection import get_db_connection
from mcp_state_server.database.repository import ConversationRepository
from mcp_state_server.models.conversation import Conversation, ConversationMessage


def load_conversation_tools(mcp_server: FastMCP) -> None:
    """
    Register conversation management tools with the MCP server.

    Args:
        mcp_server: The FastMCP server instance to register tools with.
    """
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

