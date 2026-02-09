from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, sessionmaker

import logging

from app.config import Settings


log = logging.getLogger("cozygym")
settings = Settings()


class Base(DeclarativeBase):
    pass


class Trainer(Base):
    __tablename__ = "trainers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str | None] = mapped_column(String(255))
    telegram_chat_id: Mapped[str] = mapped_column(String(64), unique=True)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    clients: Mapped[list["Client"]] = relationship(back_populates="trainer")
    tokens: Mapped[list["OAuthToken"]] = relationship(back_populates="trainer")


class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trainer_id: Mapped[int] = mapped_column(ForeignKey("trainers.id"))
    name: Mapped[str] = mapped_column(String(255))
    telegram_chat_id: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    trainer: Mapped[Trainer] = relationship(back_populates="clients")


class TrainingSession(Base):
    __tablename__ = "training_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trainer_id: Mapped[int] = mapped_column(ForeignKey("trainers.id"))
    client_id: Mapped[int | None] = mapped_column(ForeignKey("clients.id"), nullable=True)
    calendar_event_id: Mapped[str] = mapped_column(String(255), unique=True)
    summary: Mapped[str] = mapped_column(String(255))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OAuthToken(Base):
    __tablename__ = "oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trainer_id: Mapped[int] = mapped_column(ForeignKey("trainers.id"))
    access_token: Mapped[str] = mapped_column(Text)
    refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_type: Mapped[str] = mapped_column(String(32))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    trainer: Mapped[Trainer] = relationship(back_populates="tokens")


class OAuthState(Base):
    __tablename__ = "oauth_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    trainer_id: Mapped[int] = mapped_column(ForeignKey("trainers.id"))
    state: Mapped[str] = mapped_column(String(128), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


async_engine = (
    create_async_engine(settings.database_url, echo=False)
    if settings.database_url
    else None
)
AsyncSessionLocal = (
    sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)
    if async_engine
    else None
)


async def get_async_session() -> AsyncSession:
    if AsyncSessionLocal is None:
        log.error("DATABASE_URL is not configured; set DATABASE_URL or Cloud SQL connector variables.")
        raise RuntimeError("Database is not configured")
    async with AsyncSessionLocal() as session:
        yield session
