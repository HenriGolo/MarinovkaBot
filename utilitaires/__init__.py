import datetime
import traceback
from zoneinfo import ZoneInfo

import discord


class Timestamp:
    """
    Permet de facilement convertir un objet datetime en timestamp discord
    """

    def __init__(self, dt):
        if isinstance(dt, int):
            ts = dt
        elif isinstance(dt, datetime.datetime):
            ts = int(dt.timestamp())
        elif isinstance(dt, datetime.timedelta):
            dt = now() + dt
            ts = int(dt.timestamp())
        else:
            raise Exception(f"Mauvais format de {dt}")
        self.relative = f"<t:{ts}:R>"
        self.long_date = f"<t:{ts}:D>"
        self.short_date = f"<t:{ts}:d>"
        self.long_time = f"<t:{ts}:T>"
        self.short_time = f"<t:{ts}:t>"
        self.long_datetime = f"<t:{ts}:F>"
        self.short_datetime = f"<t:{ts}:f>"


class Embed(discord.Embed):
    """
    Wrapper sur les embeds discord qui permet de facilement définir un auteur
    """

    def __init__(self, *args,
                 user: discord.User | discord.Member = None,
                 guild: discord.Guild = None,
                 **kwargs):
        kwargs['timestamp'] = kwargs.get('timestamp', now())
        if hasattr(user, 'color'):
            kwargs['color'] = kwargs.get('color', user.color)
        kwargs['color'] = kwargs.get('color', 0xffffff)
        super().__init__(*args, **kwargs)
        if isinstance(guild, discord.Guild):
            self.set_author(name=guild.name, url=guild.jump_url)
            self.set_thumbnail(url=guild.icon.url)
        if isinstance(user, (discord.User, discord.Member)):
            kwargs = {
                'name': user.display_name,
                'url': user.jump_url
            }
            if hasattr(user.avatar, 'url'):
                kwargs['icon_url'] = user.avatar.url
            self.set_author(**kwargs)
            if not self.description:
                self.description = user.mention

    def add_field(self: discord.embeds.E, *, name: str, value: str, inline: bool = False) -> discord.embeds.E:
        """
        définit inline à False par défaut (au lieu de True)
        parce que True c'est moche
        """
        return super().add_field(name=name, value=value, inline=inline)


class ButtonModal(discord.ui.Button):
    def __init__(self, modal, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.modal = modal

    async def callback(self, interaction):
        await interaction.response.send_modal(self.modal)


def now(ms: bool = False, *, tz: str = 'Europe/Paris') -> datetime.datetime:
    time = datetime.datetime.now(ZoneInfo(tz))
    if not ms:
        time = time.replace(microsecond=0)
    return time


def fail(*args, **kwargs) -> str:
    # Juste du formatage
    return f"\n{traceback.format_exc(*args, **kwargs)}\n\n"
