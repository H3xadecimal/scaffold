import logging
import os
from pathlib import Path
import traceback

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
COG_DIR = Path(__file__).resolve().parent / "cogs"
log = logging.getLogger(__name__)


class ScaffoldBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix=os.getenv("PREFIX") or "!", intents=intents,
                         allowed_mentions=discord.AllowedMentions.none())

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
        # Remove globally registered slash commands from earlier versions.
        self.tree.clear_commands(guild=None)
        await self.tree.sync()


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


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.CheckFailure):
        message = "You do not have permission to use this command."
    elif isinstance(error, commands.UserInputError):
        message = f"Invalid arguments. Use {ctx.clean_prefix}help {ctx.command.qualified_name}."
    else:
        log.error("Command failed", exc_info=(type(error), error, error.__traceback__))
        message = "The command failed. Check the bot logs for details."
    await ctx.send(message)


@bot.event
async def on_ready():
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)


@bot.command(name="ping", description="Show the bot's gateway latency.")
async def ping(ctx: commands.Context):
    await ctx.send(f"Latency: {bot.latency * 1000:.2f} ms")


@bot.command(name="shutdown", description="Shut down the bot (owner only).")
@commands.is_owner()
async def shutdown(ctx: commands.Context):
    await ctx.send("Shutting down...")
    await bot.close()


@bot.command(name="reload", description="Reload one or all modules (owner only).")
@commands.is_owner()
async def reload(ctx: commands.Context, module: str | None = None):
    available = {p.stem for p in COG_DIR.glob("*.py") if p.name != "__init__.py"}
    if module is not None and module not in available:
        await ctx.send("Unknown module. Use its name without .py.")
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
    text = "\n".join(results) or "No modules found."
    for offset in range(0, len(text), 1900):
        await ctx.send(text[offset:offset + 1900])


if __name__ == "__main__":
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_TOKEN in .env before starting the bot.")
    bot.run(token)
