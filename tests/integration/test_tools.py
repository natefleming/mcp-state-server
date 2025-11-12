"""Integration tests for MCP tools using repository layer."""

import pytest

from mcp_state_server.database.connection import initialize_db_connection
from mcp_state_server.database.repository import (
    ConversationRepository,
    UserPreferencesRepository,
)
from mcp_state_server.models.conversation import Conversation, ConversationMessage
from mcp_state_server.models.user_preferences import UserPreferences


@pytest.fixture
def setup_db(test_db_connection) -> None:
    """Set up database connection for tools."""
    # Get connection details from test_db_connection
    host = test_db_connection.host
    port = test_db_connection.port
    database = test_db_connection.database
    user = test_db_connection.user
    password = test_db_connection.password

    # Initialize global connection with test database
    initialize_db_connection(
        host=host,
        port=port,
        database=database,
        user=user,
        password=password,
        use_databricks_auth=False,
    )


@pytest.mark.asyncio
async def test_save_and_get_conversation_tool(setup_db, test_db_connection) -> None:
    """Test save and get conversation tool."""
    repo = ConversationRepository(test_db_connection)

    conversation = Conversation(
        id="conv_123",
        user_id="user_456",
        title="Test Title",
    )
    saved = repo.save_conversation(conversation)
    assert saved.id == "conv_123"
    assert saved.user_id == "user_456"

    retrieved = repo.get_conversation("conv_123")
    assert retrieved is not None
    assert retrieved.id == "conv_123"


@pytest.mark.asyncio
async def test_list_conversations_tool(setup_db, test_db_connection) -> None:
    """Test list conversations tool."""
    repo = ConversationRepository(test_db_connection)

    for i in range(3):
        conversation = Conversation(
            id=f"conv_{i}",
            user_id="user_456",
            title=f"Title {i}",
        )
        repo.save_conversation(conversation)

    conversations = repo.list_conversations("user_456", limit=10)
    assert len(conversations) == 3


@pytest.mark.asyncio
async def test_save_and_get_message_tool(setup_db, test_db_connection) -> None:
    """Test save and get message tool."""
    repo = ConversationRepository(test_db_connection)

    # First create a conversation
    conversation = Conversation(
        id="conv_123",
        user_id="user_456",
    )
    repo.save_conversation(conversation)

    # Save a message
    message = ConversationMessage(
        conversation_id="conv_123",
        role="user",
        content="Hello, world!",
    )
    saved = repo.save_message(message)
    assert saved.id is not None

    messages = repo.get_messages("conv_123")
    assert len(messages) == 1
    assert messages[0].content == "Hello, world!"


@pytest.mark.asyncio
async def test_save_and_get_preference_tool(setup_db, test_db_connection) -> None:
    """Test save and get preference tool."""
    repo = UserPreferencesRepository(test_db_connection)

    preference = UserPreferences(
        user_id="user_456",
        preference_key="theme",
        preference_value="dark",
    )
    saved = repo.save_preference(preference)
    assert saved.preference_key == "theme"

    retrieved = repo.get_preference("user_456", "theme")
    assert retrieved is not None
    assert retrieved.preference_value == "dark"


@pytest.mark.asyncio
async def test_get_all_preferences_tool(setup_db, test_db_connection) -> None:
    """Test get all preferences tool."""
    repo = UserPreferencesRepository(test_db_connection)

    repo.save_preference(
        UserPreferences(
            user_id="user_456",
            preference_key="theme",
            preference_value="dark",
        )
    )
    repo.save_preference(
        UserPreferences(
            user_id="user_456",
            preference_key="language",
            preference_value="en",
        )
    )

    preferences = repo.get_all_preferences("user_456")
    assert len(preferences) == 2
