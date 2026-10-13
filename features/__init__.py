import inspect
import io

import aiohttp
import discord
from discord import ApplicationContext as AppCtx
from discord.ext import commands

from utilitaires.decorateurs import logger


class BaseAutoAddedCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot
        for name, method in inspect.getmembers(self):
            if inspect.iscoroutinefunction(method) and name.startswith("on_"):
                bot.add_listener(method, name)


class Customisation(BaseAutoAddedCog):
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
                    async with session.get(avatar_url) as resp:
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
