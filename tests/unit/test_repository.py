"""Unit tests for repository layer."""

from mcp_state_server.database.repository import (
    ConversationRepository,
    UserPreferencesRepository,
)
from mcp_state_server.models.conversation import Conversation, ConversationMessage
from mcp_state_server.models.user_preferences import UserPreferences


def test_save_conversation(test_db_connection) -> None:
    """Test saving a conversation."""
    repo = ConversationRepository(test_db_connection)
    conversation = Conversation(
        id="test_conv_1",
        user_id="user_123",
        title="Test Conversation",
    )
    saved = repo.save_conversation(conversation)
    assert saved.id == "test_conv_1"
    assert saved.user_id == "user_123"


def test_get_conversation(test_db_connection) -> None:
    """Test getting a conversation."""
    repo = ConversationRepository(test_db_connection)
    conversation = Conversation(
        id="test_conv_2",
        user_id="user_123",
        title="Test Conversation 2",
    )
    repo.save_conversation(conversation)
    retrieved = repo.get_conversation("test_conv_2")
    assert retrieved is not None
    assert retrieved.id == "test_conv_2"
    assert retrieved.user_id == "user_123"


def test_list_conversations(test_db_connection) -> None:
    """Test listing conversations."""
    repo = ConversationRepository(test_db_connection)
    for i in range(3):
        conversation = Conversation(
            id=f"test_conv_{i}",
            user_id="user_123",
            title=f"Test Conversation {i}",
        )
        repo.save_conversation(conversation)
    conversations = repo.list_conversations("user_123")
    assert len(conversations) == 3


def test_delete_conversation(test_db_connection) -> None:
    """Test deleting a conversation."""
    repo = ConversationRepository(test_db_connection)
    conversation = Conversation(
        id="test_conv_delete",
        user_id="user_123",
    )
    repo.save_conversation(conversation)
    deleted = repo.delete_conversation("test_conv_delete")
    assert deleted is True
    retrieved = repo.get_conversation("test_conv_delete")
    assert retrieved is None


def test_save_message(test_db_connection) -> None:
    """Test saving a message."""
    repo = ConversationRepository(test_db_connection)
    conversation = Conversation(id="test_conv_msg", user_id="user_123")
    repo.save_conversation(conversation)
    message = ConversationMessage(
        conversation_id="test_conv_msg",
        role="user",
        content="Test message",
    )
    saved = repo.save_message(message)
    assert saved.conversation_id == "test_conv_msg"
    assert saved.content == "Test message"


def test_get_messages(test_db_connection) -> None:
    """Test getting messages."""
    repo = ConversationRepository(test_db_connection)
    conversation = Conversation(id="test_conv_msgs", user_id="user_123")
    repo.save_conversation(conversation)
    for i in range(3):
        message = ConversationMessage(
            conversation_id="test_conv_msgs",
            role="user",
            content=f"Message {i}",
        )
        repo.save_message(message)
    messages = repo.get_messages("test_conv_msgs")
    assert len(messages) == 3


def test_save_preference(test_db_connection) -> None:
    """Test saving a preference."""
    repo = UserPreferencesRepository(test_db_connection)
    preference = UserPreferences(
        user_id="user_123",
        preference_key="theme",
        preference_value="dark",
    )
    saved = repo.save_preference(preference)
    assert saved.user_id == "user_123"
    assert saved.preference_key == "theme"
    assert saved.preference_value == "dark"


def test_get_preference(test_db_connection) -> None:
    """Test getting a preference."""
    repo = UserPreferencesRepository(test_db_connection)
    preference = UserPreferences(
        user_id="user_123",
        preference_key="language",
        preference_value="en",
    )
    repo.save_preference(preference)
    retrieved = repo.get_preference("user_123", "language")
    assert retrieved is not None
    assert retrieved.preference_value == "en"


def test_get_all_preferences(test_db_connection) -> None:
    """Test getting all preferences."""
    repo = UserPreferencesRepository(test_db_connection)
    repo.save_preference(
        UserPreferences(
            user_id="user_123", preference_key="theme", preference_value="dark"
        )
    )
    repo.save_preference(
        UserPreferences(
            user_id="user_123", preference_key="language", preference_value="en"
        )
    )
    preferences = repo.get_all_preferences("user_123")
    assert len(preferences) == 2
    assert preferences["theme"] == "dark"
    assert preferences["language"] == "en"


def test_delete_preference(test_db_connection) -> None:
    """Test deleting a preference."""
    repo = UserPreferencesRepository(test_db_connection)
    preference = UserPreferences(
        user_id="user_123",
        preference_key="temp",
        preference_value="value",
    )
    repo.save_preference(preference)
    deleted = repo.delete_preference("user_123", "temp")
    assert deleted is True
    retrieved = repo.get_preference("user_123", "temp")
    assert retrieved is None
