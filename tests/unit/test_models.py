"""Unit tests for Pydantic models."""

from mcp_state_server.models.conversation import Conversation, ConversationMessage
from mcp_state_server.models.user_preferences import UserPreferences


def test_conversation_model() -> None:
    """Test Conversation model creation."""
    conversation = Conversation(
        id="test_conv_1",
        user_id="user_123",
        title="Test Conversation",
        metadata={"key": "value"},
    )
    assert conversation.id == "test_conv_1"
    assert conversation.user_id == "user_123"
    assert conversation.title == "Test Conversation"
    assert conversation.metadata == {"key": "value"}


def test_conversation_message_model() -> None:
    """Test ConversationMessage model creation."""
    message = ConversationMessage(
        conversation_id="test_conv_1",
        role="user",
        content="Hello, world!",
    )
    assert message.conversation_id == "test_conv_1"
    assert message.role == "user"
    assert message.content == "Hello, world!"


def test_user_preferences_model() -> None:
    """Test UserPreferences model creation."""
    preference = UserPreferences(
        user_id="user_123",
        preference_key="theme",
        preference_value="dark",
    )
    assert preference.user_id == "user_123"
    assert preference.preference_key == "theme"
    assert preference.preference_value == "dark"
