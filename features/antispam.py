import asyncio
import datetime
import functools
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands, tasks

from features import BaseAutoAddedCog
from utilitaires import now, Timestamp


class AntiRaid(BaseAutoAddedCog):
    _DEFAULT_ACTIVATED = False
    _ACTIVATED = _DEFAULT_ACTIVATED
    _TIMER = 60  # Temps en minutes avant de réinitialiser l'état du filtre
    WARNINGS = dict()

    @property
    def activated(self):
        return self._ACTIVATED

    @activated.setter
    def activated(self, value: bool):
        self._ACTIVATED = value
        if value != self._DEFAULT_ACTIVATED:
            self._disarm.start(self._TIMER)

    @tasks.loop(count=1)
    async def _disarm(self, temps: int):
        await asyncio.sleep(temps * 60)
        self._ACTIVATED = self._DEFAULT_ACTIVATED

    @staticmethod
    async def is_message_raid(message: discord.Message) -> bool:
        conditions = [
            '@everyone' in message.content and len(message.attachments) == 4,
        ]
        return functools.reduce(lambda x, y: x or y, conditions, False)

    @commands.slash_command(description='(Dés)active le filtre anti-raid')
    async def anti_raid(self, ctx: discord.ApplicationContext, etat: bool = None):
        await ctx.defer(ephemeral=True)
        if etat is None:
            await ctx.respond(f'Le filtre anti-raid est actuellement {'activé' if self._ACTIVATED else 'désactivé'}')
        else:
            self.activated = etat
            await ctx.respond(f'Le filtre anti-raid a été {'activé' if self._ACTIVATED else 'désactivé'}')

    @commands.slash_command(
        description=f"Règle le timer avant de revenir à un état "
                    f"{'dés' if _DEFAULT_ACTIVATED else ''}amorcé du filtre anti-raid"
    )
    @discord.option(name='temps', description=f"Durée en minutes avant de réinitialiser l'état, actuellement {_TIMER}")
    async def anti_raid_timer(self, ctx: discord.ApplicationContext, temps: int):
        await ctx.defer(ephemeral=True)
        self._TIMER = temps
        await ctx.respond(
            f"Le filtre anti-raid sera réinitialisé après {temps} minutes d'inactivité "
            f"(ne compte pas l'itération en cours)."
        )

    async def on_message(self, message: discord.Message):
        if self.activated and not message.author.bot:
            if await self.is_message_raid(message):
                current_date = now()
                previous = datetime.datetime.fromtimestamp(
                    self.WARNINGS.get(message.author.id, 0),
                    tz=ZoneInfo('Europe/Paris')
                )
                if previous + datetime.timedelta(minutes=10) > current_date:
                    await message.author.ban(reason='Filtre anti raid', delete_message_seconds=10 * 60)
                    del self.WARNINGS[message.author.id]
                else:
                    self.WARNINGS[message.author.id] = current_date
                    await message.delete()
                    await message.author.send(
                        f"Filtre anti raid : tu as envoyé un message avec `@everyone` et 4 images, "
                        f"le message a été supprimé dans le doute.\n"
                        f"Si ton message était légitime, tu peux l'envoyer à nouveau sans `@everyone`.\n"
                        f"Si récidive d'ici {Timestamp(current_date + datetime.timedelta(minutes=10)).relative}, "
                        f"tu seras automatiquement banni du serveur.\n"
                        f"Ce message sera supprimé automatiquement à la fin de ce délai.",
                        delete_after=10 * 60
                    )
                    self.clean_warnings.start(message.author.id)

    @tasks.loop(count=1)
    async def clean_warnings(self, user_id: int):
        await asyncio.sleep(10 * 60)
        if user_id in self.WARNINGS:
            del self.WARNINGS[user_id]
