import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from agent.server import bot, start_discord_bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    bot_task = asyncio.create_task(start_discord_bot())

    try:
        yield
    finally:
        await bot.close()

        try:
            await bot_task
        except Exception:
            logger.exception("Discord bot shutdown error")


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"status": "Jared is running"}


@app.get("/health")
async def health():
    if not bot.is_ready():
        raise HTTPException(status_code=503, detail="Discord disconnected")

    return {"status": "healthy"}
