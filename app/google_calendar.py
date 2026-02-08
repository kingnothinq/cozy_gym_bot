from typing import Any

import httpx

from app.config import Settings


async def refresh_access_token(
    settings: Settings,
    *,
    code: str | None,
    refresh_token: str | None,
    is_initial: bool,
) -> dict[str, Any]:
    data = {
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": settings.google_redirect_uri,
        "grant_type": "authorization_code" if is_initial else "refresh_token",
    }
    if is_initial:
        data["code"] = code
    else:
        data["refresh_token"] = refresh_token

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post("https://oauth2.googleapis.com/token", data=data)
        response.raise_for_status()
        return response.json()


async def fetch_calendar_events(access_token: str) -> list[dict[str, Any]]:
    headers = {"Authorization": f"Bearer {access_token}"}
    params = {
        "singleEvents": True,
        "orderBy": "startTime",
        "timeMin": "1970-01-01T00:00:00Z",
    }
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.get(
            "https://www.googleapis.com/calendar/v3/calendars/primary/events",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("items", [])
