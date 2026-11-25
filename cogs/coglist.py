import discord
from discord import app_commands
from discord.ext import commands


class CogList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="cogs", description="List the currently loaded modules.")
    async def list_cogs(self, interaction: discord.Interaction):
        names = "\n".join(self.bot.cogs)
        text = f"Loaded cogs:\n{names}" if names else "No cogs are currently loaded."
        await interaction.response.send_message(text[:2000], ephemeral=True)


async def setup(bot):
    await bot.add_cog(CogList(bot))
