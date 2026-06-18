import datetime
import random

import aiohttp

from utilitaires import Embed


class Comic:
    xkcd: dict[str, str]
    XKCD_URL = 'https://xkcd.com/{number}'
    API_URL = XKCD_URL + '/info.0.json'

    def __init__(self, number: int):
        self.number = number
        self.url = self.XKCD_URL.format(number=number)
        self.api_url = self.API_URL.format(number=number)

    def __getitem__(self, item):
        return self.xkcd.__getitem__(item)

    async def fetch(self) -> dict[str, str | int]:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.api_url) as response:
                self.xkcd = await response.json()
                return self

    @staticmethod
    async def get_max_number() -> int:
        async with aiohttp.ClientSession() as session:
            print(session)
            async with session.get(Comic.API_URL.format(number='')) as response:
                print(response)
                return (await response.json())['num']

    @staticmethod
    async def get_random_number() -> int:
        return random.randint(1, await Comic.get_max_number())

    @staticmethod
    async def get_random_comic() -> 'Comic':
        return await Comic(await Comic.get_random_number()).fetch()

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
