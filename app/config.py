import os


class Settings:
    def __init__(self) -> None:
        self.telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.telegram_webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
        self.database_url = self._build_database_url()
        self.auto_migrate = os.environ.get("AUTO_MIGRATE", "false").lower() in {"1", "true", "yes"}
        self.google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self.google_redirect_uri = os.environ.get(
            "GOOGLE_REDIRECT_URI",
            "https://example.com/oauth/google/callback",
        )
        self.public_base_url = os.environ.get("PUBLIC_BASE_URL", "https://example.com")

    def _build_database_url(self) -> str:
        explicit_url = os.environ.get("DATABASE_URL", "")
        if explicit_url:
            return explicit_url

        user = os.environ.get("DB_USER", "")
        password = os.environ.get("DB_PASSWORD", "")
        name = os.environ.get("DB_NAME", "")
        cloudsql = os.environ.get("CLOUDSQL_CONNECTION_NAME", "")

        if cloudsql:
            return (
                f"postgresql+asyncpg://{user}:{password}@/{name}"
                f"?host=/cloudsql/{cloudsql}"
            )

        return ""
