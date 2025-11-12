"""User preferences model."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class UserPreferences(BaseModel):
    """Represents user preferences."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "user_456",
                "preference_key": "theme",
                "preference_value": "dark",
                "metadata": {},
            }
        }
    )

    user_id: str = Field(..., description="User ID")
    preference_key: str = Field(..., description="Preference key")
    preference_value: Any = Field(
        ..., description="Preference value (JSON-serializable)"
    )
    metadata: dict[str, Any] | None = Field(None, description="Additional metadata")
    created_at: datetime | None = Field(None, description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
