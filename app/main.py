import logging
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.storage import (
    Base,
    OAuthState,
    OAuthToken,
    Trainer,
    TrainingSession,
    Client,
    async_engine,
    get_async_session,
)
from app.config import Settings
from app.google_calendar import fetch_calendar_events, refresh_access_token
from app.schemas import (
    CalendarSyncResponse,
    HealthResponse,
    OAuthConnectedResponse,
    RootStatusResponse,
    TelegramOkResponse,
)
from app.telegram import send_telegram_message

app = FastAPI(
    title="Cozy Gym Bot API",
    description=(
        "Backend for a Telegram bot that synchronizes trainer Google Calendar events "
        "and notifies clients about upcoming trainings."
    ),
    version="1.0.0",
)
log = logging.getLogger("cozygym")
logging.basicConfig(level=logging.INFO)
settings = Settings()

@app.get("/", response_model=RootStatusResponse, tags=["system"])
async def root() -> RootStatusResponse:
    """Simple health check endpoint."""
    return {"status": "ok", "service": "cozy-gym-bot"}


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def healthcheck() -> HealthResponse:
    """Lightweight health endpoint for Cloud Run."""
    return {"status": "ok"}


@app.on_event("startup")
async def on_startup() -> None:
    if async_engine is None:
        log.error("Database engine is not configured. Skipping migrations.")
        return
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.post("/tg/webhook/{secret}", response_model=TelegramOkResponse, tags=["telegram"])
async def telegram_webhook(
    secret: str,
    request: Request,
    session: AsyncSession = Depends(get_async_session),
) -> TelegramOkResponse:
    """Handle incoming Telegram webhook updates."""
    if not settings.telegram_webhook_secret or secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=404)

    update = await request.json()
    log.info("telegram_update=%s", update)

    message = update.get("message") or update.get("edited_message")
    if not message or "text" not in message:
        return {"ok": True}

    chat_id = message["chat"]["id"]
    text = message["text"].strip()
    parts = text.split()
    command = parts[0].lower()

    if command == "/trainer":
        trainer = Trainer(name=message["from"].get("first_name"), telegram_chat_id=str(chat_id))
        session.add(trainer)
        await session.commit()
        await session.refresh(trainer)
        oauth_url = f"{settings.public_base_url}/oauth/google/start?trainer_id={trainer.id}"
        await send_telegram_message(
            settings.telegram_bot_token,
            chat_id,
            "Готово! Я создал профиль тренера.\n"
            f"ID тренера: {trainer.id}\n"
            f"Подключите Google Calendar: {oauth_url}",
        )
        return {"ok": True}

    if command == "/client" and len(parts) >= 3:
        trainer_id = int(parts[1])
        name = " ".join(parts[2:])
        client = Client(name=name, telegram_chat_id=str(chat_id), trainer_id=trainer_id)
        session.add(client)
        await session.commit()
        await send_telegram_message(
            settings.telegram_bot_token,
            chat_id,
            f"Клиент зарегистрирован у тренера {trainer_id}.",
        )
        return {"ok": True}

    if command == "/sessions":
        stmt = (
            select(TrainingSession)
            .join(Client, TrainingSession.client_id == Client.id)
            .where(Client.telegram_chat_id == str(chat_id))
            .order_by(TrainingSession.start_time)
            .limit(5)
        )
        result = await session.execute(stmt)
        sessions = result.scalars().all()
        if not sessions:
            await send_telegram_message(
                settings.telegram_bot_token,
                chat_id,
                "Ближайших тренировок пока нет.",
            )
            return {"ok": True}
        lines = [
            "Ваши ближайшие тренировки:",
            *[
                f"• {item.start_time.astimezone(timezone.utc).strftime('%d.%m %H:%M UTC')} — {item.summary}"
                for item in sessions
            ],
        ]
        await send_telegram_message(settings.telegram_bot_token, chat_id, "\n".join(lines))
        return {"ok": True}

    await send_telegram_message(
        settings.telegram_bot_token,
        chat_id,
        "Команды:\n"
        "/trainer — зарегистрировать тренера\n"
        "/client <trainer_id> <имя клиента> — зарегистрировать клиента\n"
        "/sessions — показать ближайшие тренировки",
    )
    return {"ok": True}


@app.get("/oauth/google/start", tags=["oauth"])
async def google_oauth_start(trainer_id: int, session: AsyncSession = Depends(get_async_session)):
    """Start Google OAuth flow for the specified trainer."""
    state = uuid4().hex
    session.add(OAuthState(trainer_id=trainer_id, state=state))
    await session.commit()
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": settings.google_redirect_uri,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar.readonly",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return RedirectResponse(url=f"https://accounts.google.com/o/oauth2/v2/auth?{query}")


@app.get("/oauth/google/callback", response_model=OAuthConnectedResponse, tags=["oauth"])
async def google_oauth_callback(
    code: str,
    state: str,
    session: AsyncSession = Depends(get_async_session),
) -> OAuthConnectedResponse:
    """Handle Google OAuth callback and store tokens."""
    result = await session.execute(select(OAuthState).where(OAuthState.state == state))
    oauth_state = result.scalar_one_or_none()
    if not oauth_state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    token_data = await refresh_access_token(
        settings,
        code=code,
        refresh_token=None,
        is_initial=True,
    )
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_data["expires_in"])
    token = OAuthToken(
        trainer_id=oauth_state.trainer_id,
        access_token=token_data["access_token"],
        refresh_token=token_data.get("refresh_token"),
        token_type=token_data.get("token_type", "Bearer"),
        expires_at=expires_at,
    )
    session.add(token)
    await session.delete(oauth_state)
    await session.commit()

    return {"status": "connected"}


@app.post("/calendar/sync/{trainer_id}", response_model=CalendarSyncResponse, tags=["calendar"])
async def sync_calendar(
    trainer_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> CalendarSyncResponse:
    """Synchronize Google Calendar events for a trainer and notify clients."""
    token = await session.scalar(select(OAuthToken).where(OAuthToken.trainer_id == trainer_id))
    if not token:
        raise HTTPException(status_code=400, detail="Trainer has no Google token")

    access_token = token.access_token
    if token.expires_at <= datetime.now(timezone.utc) + timedelta(minutes=1):
        refreshed = await refresh_access_token(
            settings,
            code=None,
            refresh_token=token.refresh_token,
            is_initial=False,
        )
        token.access_token = refreshed["access_token"]
        token.expires_at = datetime.now(timezone.utc) + timedelta(seconds=refreshed["expires_in"])
        await session.commit()
        access_token = token.access_token

    events = await fetch_calendar_events(access_token)
    clients = (await session.execute(select(Client).where(Client.trainer_id == trainer_id))).scalars().all()
    client_map = {client.name.lower(): client for client in clients}
    now = datetime.now(timezone.utc)
    notify_before = now + timedelta(hours=24)

    for event in events:
        summary = event.get("summary", "Тренировка")
        start = event.get("start", {}).get("dateTime")
        end = event.get("end", {}).get("dateTime")
        if not start or not end:
            continue
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))

        matched_client = None
        for name, client in client_map.items():
            if name and name in summary.lower():
                matched_client = client
                break

        session_obj = await session.scalar(
            select(TrainingSession).where(TrainingSession.calendar_event_id == event["id"])
        )
        if not session_obj:
            session_obj = TrainingSession(
                trainer_id=trainer_id,
                client_id=matched_client.id if matched_client else None,
                calendar_event_id=event["id"],
                summary=summary,
                start_time=start_dt,
                end_time=end_dt,
            )
            session.add(session_obj)
        else:
            session_obj.summary = summary
            session_obj.start_time = start_dt
            session_obj.end_time = end_dt
            if matched_client:
                session_obj.client_id = matched_client.id

        if (
            matched_client
            and session_obj.notified_at is None
            and now <= start_dt <= notify_before
        ):
            await send_telegram_message(
                settings.telegram_bot_token,
                int(matched_client.telegram_chat_id),
                f"Напоминание: тренировка {start_dt.strftime('%d.%m %H:%M')} — {summary}",
            )
            session_obj.notified_at = now

    await session.commit()
    return {"status": "synced", "events": len(events)}
