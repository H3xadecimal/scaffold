import asyncio
import logging
import os
from pathlib import Path
import traceback

import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
COG_DIR = Path(__file__).resolve().parent / "cogs"
log = logging.getLogger(__name__)


class ScaffoldBot(commands.Bot):
    def __init__(self):
        # Retain extension/Cog support without processing message commands.
        super().__init__(command_prefix=commands.when_mentioned,
                         help_command=None, intents=discord.Intents.default())

    async def on_message(self, message):
        """All commands are application commands; message content is not needed."""

    async def setup_hook(self):
        for path in sorted(COG_DIR.glob("*.py")):
            if path.name == "__init__.py":
                continue
            try:
                await self.load_extension(f"cogs.{path.stem}")
            except Exception as error:
                log.exception("Failed to load %s", path.name)
                await notify_owner_of_failure(path.name, error)
        # setup_hook runs once at login, not again on gateway reconnects.
        synced = await self.tree.sync()
        log.info("Synced %s application commands", len(synced))


bot = ScaffoldBot()


async def notify_owner_of_failure(filename, error):
    try:
        if bot.owner_id is None:
            info = await bot.application_info()
            bot.owner_id = info.team.owner_id if info.team else info.owner.id
        owner = await bot.fetch_user(bot.owner_id)
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        await owner.send(f"[FAILURE] {filename}:\n```py\n{tb[:1500]}```")
    except Exception:
        log.exception("Could not notify owner")


async def owner_only(interaction: discord.Interaction) -> bool:
    return await bot.is_owner(interaction.user)


@bot.tree.error
async def on_app_command_error(interaction, error):
    if isinstance(error, app_commands.CheckFailure):
        message = "You do not have permission to use this command."
    else:
        log.error("Application command failed", exc_info=(type(error), error, error.__traceback__))
        message = "The command failed. Check the bot logs for details."
    if interaction.response.is_done():
        await interaction.followup.send(message, ephemeral=True)
    else:
        await interaction.response.send_message(message, ephemeral=True)


@bot.event
async def on_ready():
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)


@bot.tree.command(name="ping", description="Show the bot's gateway latency.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Latency: {bot.latency * 1000:.2f} ms")


@bot.tree.command(name="shutdown", description="Shut down the bot (owner only).")
@app_commands.check(owner_only)
async def shutdown(interaction: discord.Interaction):
    await interaction.response.send_message("Shutting down...", ephemeral=True)
    await bot.close()


@bot.tree.command(name="reload", description="Reload one or all modules (owner only).")
@app_commands.describe(module="Module name without .py; omit to reload all modules")
@app_commands.check(owner_only)
async def reload(interaction: discord.Interaction, module: str | None = None):
    await interaction.response.defer(ephemeral=True, thinking=True)
    available = {p.stem for p in COG_DIR.glob("*.py") if p.name != "__init__.py"}
    if module is not None and module not in available:
        await interaction.followup.send("Unknown module. Use its name without .py.", ephemeral=True)
        return
    results = []
    for name in sorted(available if module is None else {module}):
        extension = f"cogs.{name}"
        try:
            if extension in bot.extensions:
                await bot.reload_extension(extension)
            else:
                await bot.load_extension(extension)
            results.append(f"Reloaded '{name}'.")
        except Exception as error:
            log.exception("Failed to reload %s", name)
            results.append(f"Failed to reload '{name}'; check the bot logs.")
            await notify_owner_of_failure(name, error)
    try:
        await bot.tree.sync()
    except Exception:
        log.exception("Failed to sync application commands after reload")
        results.append("Command sync failed; check the bot logs.")
    text = "\n".join(results) or "No modules found."
    for offset in range(0, len(text), 1900):
        await interaction.followup.send(text[offset:offset + 1900], ephemeral=True)


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_TOKEN in .env before starting the bot.")
    bot.run(token)
