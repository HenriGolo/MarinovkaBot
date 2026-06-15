import json
from urllib.parse import urlsplit, SplitResult, parse_qs, urlunsplit, urlencode

import discord

from utilitaires import Embed, ButtonModal, fail
from utilitaires.config import config


class AddException(discord.ui.DesignerModal):
    def __init__(self, urls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_item(
            discord.ui.Label(
                'Domaine',
                item=discord.ui.Select(
                    options=[discord.SelectOption(label=url.netloc) for url in urls],
                    placeholder='Choisir un domaine',
                    required=True)
            )
        )
        self.add_item(
            discord.ui.Label(
                'Paramètre Autorisé',
                item=discord.ui.InputText(required=True)
            )
        )

    async def callback(self, interaction: discord.Interaction):
        netloc = self.children[0].item.values[0]
        with open(Sanitizer.exceptions, 'r') as file:
            exceptions = json.load(file, **config.json_format)
        exceptions[netloc] = list(set(exceptions.get(netloc, []) + [self.children[1].item.value]))
        with open(Sanitizer.exceptions, 'w') as file:
            json.dump(exceptions, file, **config.json_format)
        await interaction.respond(
            f"Liste des exceptions pour {netloc} : {', '.join(exceptions[netloc])}",
            ephemeral=True
        )
        # Rerun l'analyse des liens
        try:
            message = interaction.message
            source = await interaction.channel.fetch_message(message.reference.message_id)
            await Sanitizer(source).sanitize(message=message)
        except Exception:
            await config.channel_logs.send(
                embed=Embed(
                    title="Sanitizer - rerun",
                    description=f"```python\n{fail().strip()}\n```",
                    color=0x00ff00
                )
            )


class Sanitizer:
    exceptions = config.get('SANITIZER_WHITELIST', 'sanitize_whitelist.json')
    try:
        with open(exceptions, 'r') as file:
            json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        with open(exceptions, 'w') as file:
            json.dump({}, file)

    def __init__(self, message: discord.Message):
        self.message = message

    def extract(self) -> list[SplitResult]:
        urls = list()
        for word in self.message.content.split(' '):
            url = urlsplit(word)
            if url.scheme and url.netloc:
                urls.append(url)
        return urls

    def _sanitize(self, url: SplitResult) -> SplitResult:
        exceptions: dict[str, list[str]] = json.load(open(self.exceptions, 'r'), **config.json_format)
        allowed = exceptions.get(url.netloc, [])
        queries = {k: v for k, v in parse_qs(url.query).items() if k in allowed}
        return url._replace(query=urlencode(queries, doseq=True))

    async def sanitize(self, *, message: discord.Message = None):
        if not self.message.author.bot:
            urls = self.extract()
            if urls:
                embed = Embed(
                    title="Liens sans trackers",
                    description="En fonction du nom de domaine, potentiellement trop fort\n"
                )
                view = discord.ui.View()
                surls = list(map(self._sanitize, urls))
                for i, surl in enumerate(surls):
                    if urlunsplit(surl) == urlunsplit(urls[i]):
                        continue

                    url = urlunsplit(surl)
                    embed.description += f"{url}\n"
                    kwargs = {
                        'url': url,
                        'label':
                            ' '.join(
                                filter(
                                    lambda s: s != 'www',
                                    surl.netloc.split('.')[:-1])
                            ).title(),
                    }
                    view.add_item(discord.ui.Button(**kwargs))
                if view.children:
                    title = "Ajouter des Exceptions"
                    view.add_item(ButtonModal(AddException(surls, title=title), label=title))
                    if message is None:
                        await self.message.reply(embed=embed, view=view, mention_author=False, silent=True)
                    else:
                        await message.edit(embed=embed, view=view)
                elif message is None:
                    await self.message.reply("C'est bien, tu as nettoyé tes liens", mention_author=False, silent=True, delete_after=1)
                else:
                    await message.delete()
