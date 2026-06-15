import io

import aiohttp
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


class Customisation(MarinovCog):
    @commands.slash_command()
    @logger
    async def avatar(self, ctx: AppCtx, nom: str = '', avatar_url: str = '', banner_url: str = ''):
        await ctx.defer(ephemeral=True)
        # Nom, PP et Bannière
        kwargs = dict()
        if nom:
            kwargs['username'] = nom
        if avatar_url or banner_url:
            async with aiohttp.ClientSession() as session:
                if avatar_url:
                    async with session.get(marinovka.icon.url) as resp:
                        img = await resp.read()
                        with io.BytesIO(img) as file:
                            kwargs['avatar'] = file.getvalue()
                if banner_url:
                    async with session.get(banner_url) as resp:
                        img = await resp.read()
                        with io.BytesIO(img) as file:
                            kwargs['banner'] = file.getvalue()
        if kwargs:
            await self.bot.user.edit(**kwargs)
            await ctx.respond("Bot modifié")
        else:
            await ctx.respond("Rien à faire")
