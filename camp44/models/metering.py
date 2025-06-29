from pydantic import BaseModel, Field


class MeterEvent(BaseModel):
    tenant_id: str  # The user_id
    app_id: str
    event_name: str
    data: dict = Field(default_factory=dict)
