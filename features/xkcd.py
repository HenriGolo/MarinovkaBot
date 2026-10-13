import datetime
import inspect
import random
from typing import Callable
from zoneinfo import ZoneInfo

import aiohttp
import discord
from discord.ext import tasks, commands

import utilitaires
from features import BaseAutoAddedCog
from utilitaires import Embed
from utilitaires.config import config
from utilitaires.decorateurs import logger
from utilitaires.json import Transaction, JsonStore

COMIC_COOLDOWN = Transaction(JsonStore(config.get('XKCD_COOLDOWN_STORAGE', 'xkcd_cooldown.json')))


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
    async def get_random_comic(cls, rng: Callable[[], int] = None) -> 'Comic':
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


class XKCD(BaseAutoAddedCog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.random_xkcd_comic.start()
        self.clear_cooldown.start()

    @tasks.loop(time=utilitaires.now().replace(hour=6, minute=0, second=0, microsecond=0).time())
    async def random_xkcd_comic(self):
        await self.bot.wait_until_ready()
        comic = await Comic.get_random_comic(Comic.get_weighted_random_number)
        with COMIC_COOLDOWN as data:
            while timestamp := data.get(comic.number):
                last_date = datetime.datetime.fromtimestamp(timestamp, tz=ZoneInfo('Europe/Paris'))
                if utilitaires.now() - last_date < datetime.timedelta(days=30):
                    comic = await Comic.get_random_comic(Comic.get_weighted_random_number)
            data[str(comic.number)] = utilitaires.now().timestamp()
        embed = comic.as_embed()
        guild = await self.bot.fetch_guild(config['GUILD_ID'])
        channel = await guild.fetch_channel(config['CHANNEL_ID_XKCD'])
        view = discord.ui.View(discord.ui.Button(label="Voir sur xkcd", url=comic.url))
        await channel.send(embed=embed, view=view)

    @tasks.loop(time=utilitaires.minuit)
    async def clear_cooldown(self):
        await self.bot.wait_until_ready()
        number_comics = await Comic.get_max_number()
        with COMIC_COOLDOWN as data:
            print(data)
            suppressions = int(number_comics / 10) * int(number_comics / 3 - len(data))
            if suppressions > 0:
                sorted_data = sorted(data.items(), key=lambda x: x[1])
                for i in range(suppressions):
                    del data[sorted_data[i][0]]

    @commands.slash_command(description='Affiche un comic xkcd aléatoire ou par numéro')
    @discord.option(name='number', description='Le numéro du comic xkcd à afficher. Aléatoire si non spécifié.')
    @logger
    async def xkcd(self, ctx: discord.ApplicationContext, number: int = None):
        await ctx.defer()
        comic = await Comic(number).fetch()
        await ctx.respond(**comic.as_message_kwargs())
