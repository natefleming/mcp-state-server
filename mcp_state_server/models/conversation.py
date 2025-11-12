"""Conversation and message models."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ConversationMessage(BaseModel):
    """Represents a single message in a conversation."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "conversation_id": "conv_123",
                "role": "user",
                "content": "Hello, how are you?",
                "metadata": {},
            }
        }
    )

    id: int | None = Field(None, description="Message ID")
    conversation_id: str = Field(..., description="Conversation ID")
    role: str = Field(..., description="Message role (user, assistant, system, tool)")
    content: str = Field(..., description="Message content")
    tool_calls: list[dict[str, Any]] | None = Field(
        None, description="Tool calls if any"
    )
    tool_call_id: str | None = Field(
        None, description="Tool call ID if this is a tool message"
    )
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")
    created_at: datetime | None = Field(None, description="Creation timestamp")


class Conversation(BaseModel):
    """Represents a conversation with messages."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "conv_123",
                "user_id": "user_456",
                "title": "My Conversation",
                "metadata": {},
            }
        }
    )

    id: str = Field(..., description="Conversation ID")
    user_id: str = Field(..., description="User ID")
    title: str | None = Field(None, description="Conversation title")
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")
    created_at: datetime | None = Field(None, description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    messages: list[ConversationMessage] | None = Field(
        None, description="Conversation messages"
    )
