# bot.py
import discord
from discord.ext import commands
from discord import app_commands
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
                print(f"[MODULE PASS] Loaded: {filename}")
            except Exception as e:
                print(f"[MODULE FAILURE] {filename}")
                traceback.print_exc()
                # async DM safely
                if bot.is_ready():  # check bot is logged in
                    asyncio.create_task(notify_owner_of_failure(filename, e))


async def notify_owner_of_failure(filename, error):
    """DMs the owner if a failure occurs with Interactions or Modules"""
    try:
        owner = await bot.fetch_user(bot.owner_id)
        tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        msg = f"[FAILURE]:\n```py\n{tb[:1900]}```"
        await owner.send(msg)
    except Exception as e:
        print(f"[WARNING] Could not DM owner: {e}")


# --- Events ---
@bot.event
async def on_ready():
    app_info = await bot.application_info()
    bot.owner_id = app_info.owner.id # Incompatible with group applications, i think.
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    await load_cogs()
    print("All systems operational.\n------")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands")
    except Exception as e:
        traceback.print_exc()
        if bot.is_ready():
            print(f"[INTERACTIONS FAILURE]", e)
            asyncio.create_task(notify_owner_of_failure(e))


# --- Core Commands ---
@bot.tree.command(name="ping", description="Gives the Latency of the Bot.")
async def ping(interaction: discord.Interaction):
    """Ping command showing latency."""
    latency = bot.latency * 1000  # seconds → ms
    await interaction.response.send_message(f"Latency: {latency:.2f} ms")

@bot.tree.command(name="shutdown", description="Shuts down the Bot.")
@commands.is_owner()
async def shutdown(interaction: discord.Interaction):
    await interaction.response.send_message("Shutting down...")
    await bot.close()

@bot.tree.command()
@commands.is_owner()
async def reload(interaction: discord.Interaction, module: str = None):
    """Reloads cogs. Use !reload or !reload <module>"""
    if module:
        try:
            await bot.reload_extension(f"cogs.{module}")
            await interaction.response.send_message(f"Reloaded '{module}'.")
        except Exception as e:
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            await interaction.response.send_message(f"Failed to reload '{module}':\n```py\n{tb[:1500]}```")
            await notify_owner_of_failure(f"{module}.py", e)
    else:
        await interaction.response.send_message("Reloading all modules...")
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                try:
                    await bot.reload_extension(f"cogs.{filename[:-3]}")
                    print(f"[RELOAD] {filename}")
                except Exception as e:
                    await notify_owner_of_failure(filename, e)
        await interaction.response.send_message("All modules reloaded.")


# --- Run ---
bot.run(TOKEN)
