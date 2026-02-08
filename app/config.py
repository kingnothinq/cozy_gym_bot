import os


class Settings:
    def __init__(self) -> None:
        self.telegram_bot_token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.telegram_webhook_secret = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
        self.database_url = os.environ.get("DATABASE_URL", "")
        self.google_client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
        self.google_client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        self.google_redirect_uri = os.environ.get(
            "GOOGLE_REDIRECT_URI",
            "https://example.com/oauth/google/callback",
        )
        self.public_base_url = os.environ.get("PUBLIC_BASE_URL", "https://example.com")
