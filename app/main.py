import os
import logging
from fastapi import FastAPI, Request, HTTPException
import httpx

app = FastAPI()
log = logging.getLogger("cozygym")
logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")

@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/tg/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if not WEBHOOK_SECRET or secret != WEBHOOK_SECRET:
        raise HTTPException(status_code=404)

    update = await request.json()
    log.info("telegram_update=%s", update)

    # Minimal echo (optional). You can remove this block later.
    try:
        message = update.get("message") or update.get("edited_message")
        if message and "text" in message:
            chat_id = message["chat"]["id"]
            text = message["text"]

            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                    json={"chat_id": chat_id, "text": f"Got it: {text}"},
                )
    except Exception as e:
        log.exception("sendMessage_failed: %s", e)

    return {"ok": True}
