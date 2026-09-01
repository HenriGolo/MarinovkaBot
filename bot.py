#!/usr/bin/env python3
import asyncio
import datetime
import importlib
import pkgutil
import urllib.parse
from pathlib import Path

from features import *
from features.sanitizer import Sanitizer
from utilitaires import now
from utilitaires.config import config


def generate_autoaddedbot_class(cogclass: type) -> type:
    class autoaddbot(discord.Bot):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            plugin_path = Path.cwd().resolve()
            self.add_module(plugin_path)

        def add_module(self, module_path):
            for _, module_name, _ in pkgutil.walk_packages(path=[str(module_path)], prefix='', onerror=print):
                for filename in (module_name, '__init__'):
                    if (file_path := module_path / f'{filename}.py').exists():
                        self.add_file(module_name, file_path)
                if (module_path / module_name).is_dir():
                    self.add_module(module_path / module_name)

        def add_file(self, module_name, file_path):
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            for obj in module.__dict__.values():
                if inspect.isclass(obj) and issubclass(obj, cogclass) and obj is not cogclass:
                    try:
                        self.add_cog(obj(self))
                    except discord.ClientException as e:
                        print(f"Error adding cog {obj.__name__}: {e}")

    return autoaddbot


AutoAddedMarinovkaBot = generate_autoaddedbot_class(MarinovCog)


class MarinovkaBot(AutoAddedMarinovkaBot):
    start_time: datetime.datetime
    invite_url: str

    async def close(self):
        # L'environnement indique de supprimer le thread
        config_delete = int(config.get('DELETE_THREAD', 0))
        # Le thread est vide (juste 1 message : celui de boot)
        aucun_message = len(await config.channel_logs.history(limit=2).flatten()) <= 1
        # Supprimer le thread pour ne garder que les logs intéressants
        if config_delete or aucun_message:
            await config.channel_logs.delete()
        # Sinon archiver proprement
        else:
            await config.channel_logs.send(f"Terminaison en douceur, uptime {now(True) - self.start_time}")
            await config.channel_logs.archive(True)
        await super().close()

    async def on_ready(self):
        # Début du bot
        self.start_time = now(True)

        self.invite_url = 'https://discord.com/oauth2/authorize?' + urllib.parse.urlencode({
            'client_id': self.user.id,
            'permissions': 8,  # Administrateur https://docs.discord.com/developers/topics/permissions
            'integration_type': 0,
            'scope': 'bot+applications.commands',
        })

        # Thread de logs
        marinovka = await self.fetch_guild(config['GUILD_ID'])
        channel_dev = await marinovka.fetch_channel(config['CHANNEL_ID_LOGS'])
        thread = await channel_dev.create_thread(name=f"Logs {self.start_time.replace(microsecond=0)}")
        print(f'{thread=}')
        await thread.send(self.invite_url)
        config.set_log_channel(thread)

        # Message de statut du bot
        activity = discord.Activity(name=marinovka.name, type=discord.ActivityType.watching)
        await self.change_presence(activity=activity)

        # Print dans la console
        if config.debug:
            print(f"Connecté en tant que {self.user}")

    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.id == self.user.id:
            if after.nick is not None or after.display_name != self.user.name:
                role: discord.Role = next(filter(lambda r: r.name == before.display_name, after.roles))
                await role.edit(name=after.nick)
                await self.user.edit(username=after.nick)
                await after.edit(nick=None)

    @staticmethod
    async def on_thread_create(thread: discord.Thread):
        await thread.join()


if __name__ == '__main__':
    MarinovkaBot(intents=discord.Intents.all()).run(token=config['TOKEN'])
