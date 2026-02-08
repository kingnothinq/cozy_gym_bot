import httpx


async def send_telegram_message(bot_token: str, chat_id: int, text: str) -> None:
    if not bot_token:
        return
    async with httpx.AsyncClient(timeout=10) as client:
        await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
