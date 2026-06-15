import discord
from discord import ApplicationContext as AppCtx
from discord.ext import commands

from utilitaires.config import config
from utilitaires.decorateurs import logger


class MarinovCog(discord.Cog):
    def __init__(self, bot):
        self.bot = bot


class HelloWorld(MarinovCog):
    @commands.slash_command(name="ping", description="ping pong", guild_ids=[int(config['GUILD_ID'])])
    @logger
    async def ping(self, ctx: AppCtx):
        await ctx.defer(ephemeral=True)
        await ctx.respond("pong")
