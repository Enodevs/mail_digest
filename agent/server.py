import asyncio
import os

import discord
from dotenv import load_dotenv

from agent.agent import ask_ai
from agent.database import save_message

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = discord.Client(intents=intents)


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")


@bot.event
async def on_message(message: discord.Message):
    # Don't respond to itself
    if message.author == bot.user:
        return

    # Ignore other bots
    if message.author.bot:
        return

    # Ignore empty messages
    if not message.content.strip():
        return

    user_message = message.content.strip()

    save_message("user", user_message)

    try:
        response = await asyncio.to_thread(
            ask_ai,
            user_message,
        )

        save_message("system", response)

        # Discord messages have a 2000-character limit
        if len(response) <= 2000:
            await message.channel.send(response)
        else:
            for i in range(0, len(response), 1900):
                await message.channel.send(
                    response[i:i + 1900]
                )

    except Exception as e:
        print(f"Error handling message: {e}")

        await message.channel.send(
            "Sorry, something went wrong while processing that."
        )


def run_discord_bot():
    if not DISCORD_BOT_TOKEN:
        raise ValueError(
            "DISCORD_BOT_TOKEN is not set."
        )

    bot.run(DISCORD_BOT_TOKEN)
