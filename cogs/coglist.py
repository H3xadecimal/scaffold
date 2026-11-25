from discord.ext import commands


class CogList(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cogs", description="List the currently loaded modules.")
    async def list_cogs(self, ctx: commands.Context):
        names = "\n".join(self.bot.cogs)
        text = f"Loaded cogs:\n{names}" if names else "No cogs are currently loaded."
        await ctx.send(text[:2000])


async def setup(bot):
    await bot.add_cog(CogList(bot))
