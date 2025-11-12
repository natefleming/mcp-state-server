"""Repository layer for database operations."""

from datetime import UTC, datetime
from typing import Any

from psycopg2.extras import Json

from mcp_state_server.database.connection import DatabaseConnection
from mcp_state_server.models.conversation import Conversation, ConversationMessage
from mcp_state_server.models.user_preferences import UserPreferences


class ConversationRepository:
    """Repository for conversation operations."""

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize conversation repository.

        Args:
            db_connection: Database connection instance
        """
        self.db = db_connection

    def save_conversation(self, conversation: Conversation) -> Conversation:
        """
        Save or update a conversation.

        Args:
            conversation: Conversation to save

        Returns:
            Saved conversation
        """
        query = """
            INSERT INTO conversations (id, user_id, title, metadata, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (id) DO UPDATE SET
                title = EXCLUDED.title,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
        """

        params = (
            conversation.id,
            conversation.user_id,
            conversation.title,
            Json(conversation.metadata or {}),
            conversation.created_at or datetime.now(UTC),
            datetime.now(UTC),
        )

        result = self.db.execute_query(query, params)
        if result:
            return self._row_to_conversation(result[0])
        return conversation

    def get_conversation(
        self, conversation_id: str, include_messages: bool = True
    ) -> Conversation | None:
        """
        Get a conversation by ID.

        Args:
            conversation_id: Conversation ID
            include_messages: Whether to include messages

        Returns:
            Conversation or None if not found
        """
        query = "SELECT * FROM conversations WHERE id = %s"
        result = self.db.execute_query(query, (conversation_id,))

        if not result:
            return None

        conversation = self._row_to_conversation(result[0])

        if include_messages:
            conversation.messages = self.get_messages(conversation_id)

        return conversation

    def list_conversations(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Conversation]:
        """
        List conversations for a user.

        Args:
            user_id: User ID
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            List of conversations
        """
        query = """
            SELECT * FROM conversations
            WHERE user_id = %s
            ORDER BY updated_at DESC
            LIMIT %s OFFSET %s
        """

        result = self.db.execute_query(query, (user_id, limit, offset))
        return [self._row_to_conversation(row) for row in result or []]

    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation and all its messages.

        Args:
            conversation_id: Conversation ID

        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM conversations WHERE id = %s RETURNING id"
        result = self.db.execute_query(query, (conversation_id,))
        return result is not None and len(result) > 0

    def save_message(self, message: ConversationMessage) -> ConversationMessage:
        """
        Save a message.

        Args:
            message: Message to save

        Returns:
            Saved message
        """
        query = """
            INSERT INTO messages (
                conversation_id, role, content, tool_calls, tool_call_id, metadata, created_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING *
        """

        params = (
            message.conversation_id,
            message.role,
            message.content,
            Json(message.tool_calls) if message.tool_calls else None,
            message.tool_call_id,
            Json(message.metadata or {}),
            message.created_at or datetime.now(UTC),
        )

        result = self.db.execute_query(query, params)
        if result:
            return self._row_to_message(result[0])
        return message

    def get_messages(self, conversation_id: str) -> list[ConversationMessage]:
        """
        Get all messages for a conversation.

        Args:
            conversation_id: Conversation ID

        Returns:
            List of messages
        """
        query = """
            SELECT * FROM messages
            WHERE conversation_id = %s
            ORDER BY created_at ASC
        """

        result = self.db.execute_query(query, (conversation_id,))
        return [self._row_to_message(row) for row in result or []]

    def delete_message(self, message_id: int) -> bool:
        """
        Delete a message.

        Args:
            message_id: Message ID

        Returns:
            True if deleted, False if not found
        """
        query = "DELETE FROM messages WHERE id = %s RETURNING id"
        result = self.db.execute_query(query, (message_id,))
        return result is not None and len(result) > 0

    def _row_to_conversation(self, row: dict[str, Any]) -> Conversation:
        """Convert database row to Conversation model."""
        return Conversation(
            id=row["id"],
            user_id=row["user_id"],
            title=row.get("title"),
            metadata=row.get("metadata") or {},
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def _row_to_message(self, row: dict[str, Any]) -> ConversationMessage:
        """Convert database row to ConversationMessage model."""
        return ConversationMessage(
            id=row["id"],
            conversation_id=row["conversation_id"],
            role=row["role"],
            content=row["content"],
            tool_calls=row.get("tool_calls"),
            tool_call_id=row.get("tool_call_id"),
            metadata=row.get("metadata") or {},
            created_at=row.get("created_at"),
        )


class UserPreferencesRepository:
    """Repository for user preferences operations."""

    def __init__(self, db_connection: DatabaseConnection) -> None:
        """
        Initialize user preferences repository.

        Args:
            db_connection: Database connection instance
        """
        self.db = db_connection

    def save_preference(self, preference: UserPreferences) -> UserPreferences:
        """
        Save or update a user preference.

        Args:
            preference: Preference to save

        Returns:
            Saved preference
        """
        query = """
            INSERT INTO user_preferences (
                user_id, preference_key, preference_value, metadata, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, preference_key) DO UPDATE SET
                preference_value = EXCLUDED.preference_value,
                metadata = EXCLUDED.metadata,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
        """

        params = (
            preference.user_id,
            preference.preference_key,
            Json(preference.preference_value),
            Json(preference.metadata or {}),
            preference.created_at or datetime.now(UTC),
            datetime.now(UTC),
        )

        result = self.db.execute_query(query, params)
        if result:
            return self._row_to_preference(result[0])
        return preference

    def get_preference(
        self, user_id: str, preference_key: str
    ) -> UserPreferences | None:
        """
        Get a user preference.

        Args:
            user_id: User ID
            preference_key: Preference key

        Returns:
            Preference or None if not found
        """
        query = """
            SELECT * FROM user_preferences
            WHERE user_id = %s AND preference_key = %s
        """

        result = self.db.execute_query(query, (user_id, preference_key))
        if result:
            return self._row_to_preference(result[0])
        return None

    def get_all_preferences(self, user_id: str) -> dict[str, Any]:
        """
        Get all preferences for a user.

        Args:
            user_id: User ID

        Returns:
            Dictionary of preference_key -> preference_value
        """
        query = """
            SELECT preference_key, preference_value FROM user_preferences
            WHERE user_id = %s
        """

        result = self.db.execute_query(query, (user_id,))
        return {row["preference_key"]: row["preference_value"] for row in result or []}

    def delete_preference(self, user_id: str, preference_key: str) -> bool:
        """
        Delete a user preference.

        Args:
            user_id: User ID
            preference_key: Preference key

        Returns:
            True if deleted, False if not found
        """
        query = """
            DELETE FROM user_preferences
            WHERE user_id = %s AND preference_key = %s
            RETURNING preference_key
        """

        result = self.db.execute_query(query, (user_id, preference_key))
        return result is not None and len(result) > 0

    def delete_all_preferences(self, user_id: str) -> int:
        """
        Delete all preferences for a user.

        Args:
            user_id: User ID

        Returns:
            Number of preferences deleted
        """
        query = (
            "DELETE FROM user_preferences WHERE user_id = %s RETURNING preference_key"
        )
        result = self.db.execute_query(query, (user_id,))
        return len(result) if result else 0

    def _row_to_preference(self, row: dict[str, Any]) -> UserPreferences:
        """Convert database row to UserPreferences model."""
        return UserPreferences(
            user_id=row["user_id"],
            preference_key=row["preference_key"],
            preference_value=row["preference_value"],
            metadata=row.get("metadata") or {},
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )
