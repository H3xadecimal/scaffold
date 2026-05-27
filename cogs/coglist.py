# cogs/coglist.py
from discord.ext import commands

class CogList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cogs")
    async def list_cogs(self, ctx):
        """Lists all loaded cogs including this one."""
        cogs = list(self.bot.cogs.keys())
        if cogs:
            cog_list = "\n".join(cogs)
            await ctx.send(f"Loaded cogs:\n{cog_list}")
        else:
            await ctx.send("No cogs are currently loaded.")

async def setup(bot):
    await bot.add_cog(CogList(bot))
