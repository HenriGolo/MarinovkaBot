import datetime
import urllib.parse

from cogs import *
from utilitaires import now
from utilitaires.config import config


class MarinovkaBot(discord.AutoShardedBot):
    start_time: datetime.datetime
    invite_url = 'https://discord.com/oauth2/authorize?' + urllib.parse.urlencode({
        'client_id': config['CLIENT_ID'],
        'permissions': 8,  # Administrateur https://docs.discord.com/developers/topics/permissions
        'integration_type': 0,
        'scope': 'bot+applications.commands',
    })

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for cog in MarinovCog.__subclasses__():
            self.add_cog(cog(self))

    async def close(self):
        await config.channel_logs.send(f"Terminaison en douceur, uptime {now(True) - self.start_time}")
        await config.channel_logs.archive(True)
        if int(config.get('DELETE_THREAD', 0)):
            await config.channel_logs.delete()
        await super().close()

    async def on_ready(self):
        # Début du bot
        self.start_time = now(True)

        # Thread de logs
        marinovka = await self.fetch_guild(config['GUILD_ID'])
        channel_dev = await marinovka.fetch_channel(config['CHANNEL_ID'])
        thread = await channel_dev.create_thread(name=f"Logs {self.start_time.replace(microsecond=0)}")
        await thread.send(self.invite_url)
        config.set_log_channel(thread)
        # Print dans la console
        print(f"Connecté en tant que {self.user}")


if __name__ == '__main__':
    MarinovkaBot(intents=discord.Intents.all()).run(token=config['TOKEN'])
