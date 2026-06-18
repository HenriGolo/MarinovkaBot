import json
from urllib.parse import urlsplit, SplitResult, parse_qs, parse_qsl, urlunsplit, urlencode

import discord

from utilitaires import Embed, ButtonModal, fail
from utilitaires.config import config


def short_netloc(netloc: str):
    return netloc.replace('www.', '')


class AddException(discord.ui.DesignerModal):
    def __init__(self, urls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_item(
            discord.ui.Label(
                'Domaine',
                item=discord.ui.Select(
                    options=[discord.SelectOption(label=short_netloc(url.netloc)) for url in urls],
                    placeholder='Choisir un domaine',
                    required=True)
            )
        )
        self.add_item(
            discord.ui.Label(
                'Paramètre Autorisé',
                item=discord.ui.Select(
                    options=[discord.SelectOption(label=q[0], description=q[1]) for url in urls for q in
                             parse_qsl(url.query)],
                    placeholder='Ajouter une query',
                    required=True,
                    max_values=len(sum((parse_qsl(url.query) for url in urls), []))
                )
            )
        )

    async def callback(self, interaction: discord.Interaction):
        netloc = self.children[0].item.values[0]
        short = short_netloc(netloc)
        with open(Sanitizer.exceptions, 'r') as file:
            exceptions = json.load(file, **config.json_format)
        exceptions[short] = list(set(exceptions.get(short, []) + self.children[1].item.values))
        with open(Sanitizer.exceptions, 'w') as file:
            json.dump(exceptions, file, **config.json_format)
        await interaction.respond(
            f"Liste des exceptions pour {short} : {', '.join(exceptions[short])}",
            ephemeral=True,
            delete_after=3,
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

    @staticmethod
    def _sanitize(url: SplitResult, exceptions: dict[str, list[str]]) -> SplitResult:
        allowed = exceptions.get(short_netloc(url.netloc), [])
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
                with open(self.exceptions, 'r') as file:
                    exceptions = json.load(file, **config.json_format)
                surls = list(map(lambda u: self._sanitize(u, exceptions), urls))
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
                    view.add_item(ButtonModal(AddException(urls, title=title), label=title))
                    if message is None:
                        await self.message.reply(embed=embed, view=view, mention_author=False, silent=True)
                    else:
                        await message.edit(embed=embed, view=view)
                elif message is None:
                    await self.message.reply("C'est bien, tu as nettoyé tes liens", mention_author=False, silent=True, delete_after=1)
                else:
                    await message.delete()
