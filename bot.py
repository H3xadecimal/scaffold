# bot.py
import discord
from discord.ext import commands
import os
import traceback
import asyncio
from dotenv import load_dotenv
load_dotenv()

# --- CONFIG ---
TOKEN = os.getenv("DISCORD_TOKEN")
PREFIX = os.getenv("PREFIX")
# --------------

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)


# --- Module Loader ---
async def load_cogs():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py") and filename != "__init__.py":
            cog_name = filename[:-3]
            try:
                await bot.load_extension(f"cogs.{cog_name}")  # await it
                print(f"[OK] Loaded: {filename}")
            except Exception as e:
                print(f"[FAIL] {filename}")
                traceback.print_exc()
                # async DM safely
                if bot.is_ready():  # check bot is logged in
                    asyncio.create_task(notify_owner_of_failure(filename, e))


async def notify_owner_of_failure(filename, error):
    """DMs the owner if a cog fails to load."""
    try:
        owner = await bot.fetch_user(bot.owner_id)
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        msg = f"Module '{filename}' failed to load:\n```py\n{tb[:1900]}```"
        await owner.send(msg)
    except Exception as e:
        print(f"[WARN] Could not DM owner: {e}")


# --- Events ---
@bot.event
async def on_ready():
    app_info = await bot.application_info()
    bot.owner_id = app_info.owner.id # Incompatible with group applications, i think.
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await load_cogs()
    print("All systems operational.\n------")


# --- Core Commands ---
@bot.command()
async def ping(ctx):
    """Ping command showing latency."""
    latency = bot.latency * 1000  # seconds → ms
    await ctx.send(f"Latency: {latency:.2f} ms")

@bot.command()
@commands.is_owner()
async def shutdown(ctx):
    """Safely shuts down the bot."""
    await ctx.send("Shutting down...")
    await bot.close()

@bot.command()
@commands.is_owner()
async def reload(ctx, module: str = None):
    """Reloads cogs. Use !reload or !reload <module>"""
    if module:
        try:
            await bot.reload_extension(f"cogs.{module}")
            await ctx.send(f"Reloaded '{module}'.")
        except Exception as e:
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            await ctx.send(f"Failed to reload '{module}':\n```py\n{tb[:1500]}```")
            await notify_owner_of_failure(f"{module}.py", e)
    else:
        await ctx.send("Reloading all modules...")
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                try:
                    await bot.reload_extension(f"cogs.{filename[:-3]}")
                    print(f"[RELOAD] {filename}")
                except Exception as e:
                    await notify_owner_of_failure(filename, e)
        await ctx.send("All modules reloaded.")


# --- Run ---
bot.run(TOKEN)
