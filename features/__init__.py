import io

import aiohttp
import discord
from discord import ApplicationContext as AppCtx
from discord.ext import tasks, commands

from features import xkcd
from utilitaires import now
from utilitaires.config import config
from utilitaires.decorateurs import logger


class MarinovCog(discord.Cog):
    def __init__(self, bot: discord.Bot):
        self.bot = bot


class Repetitions(MarinovCog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.random_xkcd_comic.start()

    # à minuit heure de paris
    @tasks.loop(time=now().replace(hour=6, minute=0, second=0).time())
    async def random_xkcd_comic(self):
        await self.bot.wait_until_ready()
        comic = await xkcd.Comic.get_random_comic()
        embed = comic.as_embed()
        marinovka = await self.bot.fetch_guild(config['GUILD_ID'])
        channel = await marinovka.fetch_channel(config['CHANNEL_ID_XKCD'])
        view = discord.ui.View(discord.ui.Button(label="Voir sur xkcd", url=comic.url))
        await channel.send(embed=embed, view=view)


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
