"""Integration tests for MCP server over HTTP/SSE.

These tests connect to a deployed Databricks App MCP server using SSE transport.
To run these tests, you need to:

1. Set the MCP_SERVER_URL environment variable (or use the default):
   export MCP_SERVER_URL=https://your-app-url.azure.databricksapps.com

2. Configure Databricks authentication:
   - Set DATABRICKS_TOKEN environment variable with a valid token, OR
   - Configure Databricks CLI/SDK authentication (databricks configure --token)

The tests will skip if authentication is not available.
"""

import os

import httpx
import pytest
from databricks.sdk import WorkspaceClient
from mcp import ClientSession
from mcp.client.sse import sse_client


@pytest.fixture
def mcp_server_url() -> str:
    """Get MCP server URL from environment or use default."""
    base_url = os.getenv(
        "MCP_SERVER_URL",
        "https://mcp-state-server-984752964297111.11.azure.databricksapps.com",
    )
    # FastMCP SSE transport uses /messages-sse endpoint
    if not base_url.endswith("/messages-sse"):
        base_url = base_url.rstrip("/") + "/messages-sse"
    return base_url


@pytest.fixture
def databricks_auth() -> httpx.Auth | None:
    """Get Databricks authentication for MCP client."""
    try:
        workspace_client = WorkspaceClient()
        # Try to get token from config
        # For service principals, token might be in config.token
        # For OAuth, we might need to use the SDK's authentication mechanism
        token: str | None = None

        # Check if token is directly available
        # Use getattr with default None instead of hasattr for strongly typed objects
        config_token = getattr(workspace_client.config, "token", None)
        if config_token:
            token = config_token

        # If no token found, try to authenticate and get one
        if not token:
            # For Databricks Apps, authentication might be handled via cookies/session
            # In this case, we'll skip authentication and let the test handle it
            # or use environment variable for token
            token = os.getenv("DATABRICKS_TOKEN")

        if token:
            # Create a simple auth handler that adds the Bearer token
            class DatabricksAuth(httpx.Auth):
                def __init__(self, token: str) -> None:
                    self.token = token

                def auth_flow(self, request: httpx.Request) -> httpx.Request:
                    request.headers["Authorization"] = f"Bearer {self.token}"
                    return request

            return DatabricksAuth(token)
    except Exception as e:
        # Log the exception for debugging
        import sys

        print(f"Warning: Could not get Databricks authentication: {e}", file=sys.stderr)
        # If authentication fails, return None (tests will need to handle this)
        return None
    return None


@pytest.mark.asyncio
async def test_mcp_server_connection(
    mcp_server_url: str, databricks_auth: httpx.Auth | None
) -> None:
    """Test basic connection to MCP server."""
    if databricks_auth is None:
        pytest.skip("Databricks authentication not available")

    async with sse_client(mcp_server_url, auth=databricks_auth) as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            assert tools is not None
            assert len(tools.tools) > 0

            # Verify expected tools exist
            tool_names = [tool.name for tool in tools.tools]
            assert "save_conversation_tool" in tool_names
            assert "get_conversation_tool" in tool_names
            assert "list_conversations_tool" in tool_names


@pytest.mark.asyncio
async def test_save_and_get_conversation(
    mcp_server_url: str, databricks_auth: httpx.Auth | None
) -> None:
    """Test saving and retrieving a conversation."""
    if databricks_auth is None:
        pytest.skip("Databricks authentication not available")

    async with sse_client(mcp_server_url, auth=databricks_auth) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Save a conversation
            result = await session.call_tool(
                "save_conversation_tool",
                arguments={
                    "conversation_id": "test_conv_integration",
                    "user_id": "test_user_integration",
                    "title": "Integration Test Conversation",
                },
            )
            assert result is not None
            assert len(result.content) > 0

            # Get the conversation
            result = await session.call_tool(
                "get_conversation_tool",
                arguments={
                    "conversation_id": "test_conv_integration",
                    "include_messages": True,
                },
            )
            assert result is not None
            assert len(result.content) > 0
            assert "test_conv_integration" in result.content[0].text


@pytest.mark.asyncio
async def test_save_and_get_message(
    mcp_server_url: str, databricks_auth: httpx.Auth | None
) -> None:
    """Test saving and retrieving messages."""
    if databricks_auth is None:
        pytest.skip("Databricks authentication not available")

    async with sse_client(mcp_server_url, auth=databricks_auth) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # First create a conversation
            await session.call_tool(
                "save_conversation_tool",
                arguments={
                    "conversation_id": "test_msg_conv",
                    "user_id": "test_user_msg",
                },
            )

            # Save a message
            result = await session.call_tool(
                "save_message_tool",
                arguments={
                    "conversation_id": "test_msg_conv",
                    "role": "user",
                    "content": "Test message from integration test",
                },
            )
            assert result is not None

            # Get messages
            result = await session.call_tool(
                "get_messages_tool",
                arguments={"conversation_id": "test_msg_conv"},
            )
            assert result is not None
            assert len(result.content) > 0
            assert "Test message" in result.content[0].text


@pytest.mark.asyncio
async def test_save_and_get_preference(
    mcp_server_url: str, databricks_auth: httpx.Auth | None
) -> None:
    """Test saving and retrieving user preferences."""
    if databricks_auth is None:
        pytest.skip("Databricks authentication not available")

    async with sse_client(mcp_server_url, auth=databricks_auth) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Save a preference
            result = await session.call_tool(
                "save_preference_tool",
                arguments={
                    "user_id": "test_user_pref",
                    "preference_key": "theme",
                    "preference_value": "dark",
                },
            )
            assert result is not None

            # Get the preference
            result = await session.call_tool(
                "get_preference_tool",
                arguments={
                    "user_id": "test_user_pref",
                    "preference_key": "theme",
                },
            )
            assert result is not None
            assert len(result.content) > 0
            assert "dark" in result.content[0].text.lower()


@pytest.mark.asyncio
async def test_list_conversations(
    mcp_server_url: str, databricks_auth: httpx.Auth | None
) -> None:
    """Test listing conversations for a user."""
    if databricks_auth is None:
        pytest.skip("Databricks authentication not available")

    async with sse_client(mcp_server_url, auth=databricks_auth) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # Create a few conversations
            for i in range(3):
                await session.call_tool(
                    "save_conversation_tool",
                    arguments={
                        "conversation_id": f"test_list_conv_{i}",
                        "user_id": "test_user_list",
                        "title": f"Test Conversation {i}",
                    },
                )

            # List conversations
            result = await session.call_tool(
                "list_conversations_tool",
                arguments={
                    "user_id": "test_user_list",
                    "limit": 10,
                    "offset": 0,
                },
            )
            assert result is not None
            assert len(result.content) > 0
