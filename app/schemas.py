from pydantic import BaseModel, Field


class RootStatusResponse(BaseModel):
    status: str = Field(..., example="ok")
    service: str = Field(..., example="cozy-gym-bot")


class HealthResponse(BaseModel):
    status: str = Field(..., example="ok")


class TelegramOkResponse(BaseModel):
    ok: bool = Field(..., example=True)


class OAuthConnectedResponse(BaseModel):
    status: str = Field(..., example="connected")


class CalendarSyncResponse(BaseModel):
    status: str = Field(..., example="synced")
    events: int = Field(..., example=5)
