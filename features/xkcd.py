import datetime
import inspect
import random

import aiohttp
import discord
from discord.ext import tasks, commands

import utilitaires
from features import MarinovCog
from utilitaires import Embed
from utilitaires.config import config


class Comic:
    xkcd: dict[str, str]
    XKCD_URL = 'https://xkcd.com/{number}'
    API_URL = XKCD_URL + '/info.0.json'
    api_url: str
    url: str

    def __init__(self, number: int = None):
        self._number = None
        self.number = number

    @property
    def number(self):
        return self._number

    @number.setter
    def number(self, value):
        self._number = value
        self.url = self.XKCD_URL.format(number=self._number)
        self.api_url = self.API_URL.format(number=self._number)

    def __getitem__(self, item):
        return self.xkcd.__getitem__(item)

    async def fetch(self) -> 'Comic':
        if self.number is None or not hasattr(self, 'api_url') or self.api_url is None:
            self.number = await self.get_random_number()
        async with aiohttp.ClientSession() as session:
            async with session.get(self.api_url) as response:
                self.xkcd = await response.json()
                return self

    @classmethod
    async def get_max_number(cls) -> int:
        async with aiohttp.ClientSession() as session:
            async with session.get(cls.API_URL.format(number='')) as response:
                return (await response.json())['num']

    @classmethod
    async def get_random_number(cls) -> int:
        return random.randint(1, await cls.get_max_number())

    @classmethod
    async def get_weighted_random_number(cls) -> int:
        max_number = await cls.get_max_number()
        # Plus grande probabilité pour les numéros récents
        weights = [1 / (max_number - i + 1) for i in range(max_number)]
        return random.choices(range(1, max_number + 1), weights=weights)[0]

    @classmethod
    async def get_weighted_random_comic(cls) -> 'Comic':
        number = await cls.get_weighted_random_number()
        return await cls(number).fetch()

    @classmethod
    async def get_random_comic(cls, rng=None) -> 'Comic':
        if rng is None:
            rng = cls.get_random_number
        random_number = await rng() if inspect.iscoroutinefunction(rng) else rng()
        return await Comic(random_number).fetch()

    def as_embed(self) -> Embed:
        timestamp = datetime.datetime.strptime(f"{self['year']}-{self['month']}-{self['day']}", '%Y-%m-%d')
        embed = Embed(
            title=self['title'],
            image=self['img'],
            timestamp=timestamp,
            url=Comic.XKCD_URL.format(number=self['num'])
        )
        embed.set_footer(text=f"#{self['num']}", icon_url='https://xkcd.com/s/0b7742.png')
        return embed

    def as_view(self, *, view_class: type = discord.ui.View, **kwargs) -> discord.ui.View:
        return view_class(discord.ui.Button(label="Voir sur xkcd", url=self.url), **kwargs)

    def as_message_kwargs(self):
        return {
            'embed': self.as_embed(),
            'view': self.as_view()
        }


class XKCD(MarinovCog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.random_xkcd_comic.start()

    @tasks.loop(time=utilitaires.now().replace(hour=6, minute=0, second=0, microsecond=0).time())
    async def random_xkcd_comic(self):
        await self.bot.wait_until_ready()
        comic = await Comic.get_random_comic(Comic.get_weighted_random_number)
        embed = comic.as_embed()
        marinovka = await self.bot.fetch_guild(config['GUILD_ID'])
        channel = await marinovka.fetch_channel(config['CHANNEL_ID_XKCD'])
        view = discord.ui.View(discord.ui.Button(label="Voir sur xkcd", url=comic.url))
        await channel.send(embed=embed, view=view)

    @commands.slash_command(description='Affiche un comic xkcd aléatoire ou par numéro')
    @discord.option(name='number', description='Le numéro du comic xkcd à afficher. Aléatoire si non spécifié.')
    async def xkcd(self, ctx: discord.ApplicationContext, number: int = None):
        await ctx.defer()
        comic = await Comic(number).fetch()
        await ctx.respond(**comic.as_message_kwargs())
