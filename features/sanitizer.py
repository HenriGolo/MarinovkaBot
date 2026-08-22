import copy
from urllib.parse import urlsplit, SplitResult, parse_qs, parse_qsl, urlunsplit, urlencode

import discord
from discord.ext import commands, tasks

import utilitaires
from features import MarinovCog
from utilitaires import Embed, ButtonModal, fail
from utilitaires.config import config
from utilitaires.json import Transaction, JsonStore


def domain_select(urls: list[SplitResult], **kwargs):
    return discord.ui.Select(
        options=[
            discord.SelectOption(label=short_netloc(url.netloc), default=len(urls) == 1)
            for url in urls
        ],
        **kwargs
    )


def short_netloc(netloc: str):
    filtered = netloc.replace('www.', '')
    return {
        'youtu.be': 'youtube.com',
        'redd.it': 'reddit.com',
    }.get(filtered, filtered)


class RerunSanitize(discord.ui.Button):
    async def callback(self, interaction: discord.Interaction):
        await Sanitizer.run(interaction.message)


class AddException(discord.ui.DesignerModal):
    def __init__(self, urls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_item(
            discord.ui.Label(
                'Domaine',
                item=domain_select(
                    urls,
                    placeholder='Choisir un domaine',
                    required=True
                ),
            )
        )
        self.add_item(
            discord.ui.Label(
                'Paramètre Autorisé',
                item=discord.ui.Select(
                    options=[
                        discord.SelectOption(label=label, description=description)
                        for url in urls
                        for label, description in parse_qsl(url.query)
                    ],
                    placeholder='Ajouter une query',
                    required=True,
                    max_values=len(sum((parse_qsl(url.query) for url in urls), []))
                )
            )
        )

    @staticmethod
    def valid_urls(urls: list[SplitResult]) -> list[SplitResult]:
        return [url for url in urls if parse_qsl(url.query)]

    async def callback(self, interaction: discord.Interaction):
        netloc = self.children[0].item.values[0]
        short = short_netloc(netloc)
        with Sanitizer.exceptions as exceptions:
            exceptions[short] = list(set(exceptions.get(short, []) + self.children[1].item.values))
            await interaction.respond(
                f"Liste des exceptions pour {short} : {', '.join(exceptions[short])}",
                ephemeral=True,
                delete_after=3,
            )
        # Rerun l'analyse des liens
        await Sanitizer.run(interaction.message)


class RenderLink(discord.ui.DesignerModal):
    renders = Transaction(JsonStore(config.get('SANITIZER_RENDER', 'sanitize_render.json')))

    def __init__(self, urls, *args, **kwargs):
        super().__init__(*args, **kwargs)
        index = -1
        self.domain_index = (index := index + 1)
        self.add_item(
            discord.ui.Label(
                'Domaine',
                item=domain_select(
                    urls,
                    placeholder='Choisir un domaine',
                    required=True
                )
            )
        )
        default_checkbox = True
        with self.renders as renders:
            alternatives = [
                link
                for url in urls
                for link in renders.get(short_netloc(url.netloc), []).get('available', [])
            ]
        if alternatives:
            default_checkbox = False
            self.link_index = (index := index + 1)
            self.add_item(
                discord.ui.Label(
                    'Lien Alternatif',
                    item=discord.ui.Select(
                        options=[
                            discord.SelectOption(label=link)
                            for link in alternatives
                        ],
                        placeholder='Choisir un lien alternatif',
                        required=False
                    )
                )
            )
        self.new_domain_index = (index := index + 1)
        self.add_item(
            discord.ui.Label(
                'Ajouter Nouveau',
                item=discord.ui.InputText(
                    placeholder='Nom de domaine sans https:// ni www.',
                    required=False
                )
            )
        )
        self.default_index = (index := index + 1)
        self.add_item(
            discord.ui.Label(
                'Définir par défaut',
                item=discord.ui.Checkbox(default=default_checkbox)
            )
        )

    async def callback(self, interaction: discord.Interaction):
        # Récupère le domaine sélectionné
        domain = self.children[self.domain_index].item.values[0]
        # Récupère le lien alternatif sélectionné, s'il existe
        alternative = (
            self.children[self.link_index].item.values[0]
            if self.children[self.link_index].item.values else None
        ) if hasattr(self, 'link_index') else None
        # Récupère le nouveau domaine saisi, s'il existe
        new_domain = (
            self.children[self.new_domain_index].item.value.strip()
        ) if self.children[self.new_domain_index].item.value else None
        # Récupère le booléen indiquant si le lien doit être défini par défaut
        default = self.children[self.default_index].item
        # Vérifie qu'un lien alternatif ou un nouveau domaine a été fourni
        if not alternative and not new_domain:
            return await interaction.respond('Il faut renseigner un domaine existant ou un nouveau', ephemeral=True)
        with self.renders as renders:
            renders[domain] = renders.get(domain, {})
            renders[domain]['available'] = list(set(renders[domain].get('available', []) + [new_domain or alternative]))
            if default or not renders[domain].get('default'):
                renders[domain]['default'] = new_domain or alternative
            if not renders[domain]['default'] in renders[domain]['available']:
                renders[domain]['available'] += [renders[domain]['default']]
        return await interaction.respond(f'Rendu ajouté pour {domain} : {new_domain or alternative}', ephemeral=True)


class Sanitizer:
    exceptions = Transaction(JsonStore(config.get('SANITIZER_WHITELIST', 'sanitize_whitelist.json')))

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
    async def run(message: discord.Message):
        try:
            source = await message.channel.fetch_message(message.reference.message_id)
            await Sanitizer(source).sanitize(message=message)
        except Exception:
            await config.channel_logs.send(
                embed=Embed(
                    title="Sanitizer - rerun",
                    description=f"```python\n{fail().strip()}\n```",
                    color=0x00ff00
                )
            )

    @staticmethod
    def _sanitize(url: SplitResult, exceptions: dict[str, list[str]]) -> SplitResult:
        allowed = exceptions.get(short_netloc(url.netloc), [])
        queries = {k: v for k, v in parse_qs(url.query).items() if k in allowed}
        return url._replace(query=urlencode(queries, doseq=True))

    # Update le message passé en paramètre, ou en crée un nouveau
    async def sanitize(self, *, message: discord.Message = None) -> discord.Message | None:
        if not self.message.author.bot:
            urls = self.extract()
            if urls:
                content = 'Liens sans trackers et mieux rendus (potentiellement trop fort)\n'
                view = discord.ui.View()
                with self.exceptions as exceptions:
                    surls: list[SplitResult] = list(map(lambda u: self._sanitize(u, exceptions), urls))
                raw_surls = [surl._replace(netloc=short_netloc(surl.netloc)) for surl in surls]
                different_render = False
                for i, surl in enumerate(surls):
                    with RenderLink.renders as renders:
                        if has_render := (sn := short_netloc(surl.netloc)) in renders:
                            if (default := renders[sn].get('default')) is not None:
                                different_render = True
                                surl = surl._replace(netloc=default)
                    if not has_render and urlunsplit(surl) == urlunsplit(urls[i]):
                        continue

                    url = urlunsplit(surl)
                    raw_surl = raw_surls[i]
                    content += f"{url}\n"
                    view.add_item(
                        discord.ui.Button(
                            url=urlunsplit(raw_surl),
                            label=''.join(
                                filter(
                                    lambda s: s != 'www',
                                    raw_surl.netloc.split('.')[:-1]
                                )
                            )
                        )
                    )
                if view.children:
                    title = 'Ajouter des Exceptions'
                    if filtered := AddException.valid_urls(urls):
                        view.add_item(ButtonModal(AddException(filtered, title=title), label=title))
                if different_render:
                    title = 'Rendu des liens'
                    view.add_item(ButtonModal(RenderLink(urls, title=title), label=title))
                if view.children:
                    view.add_item(RerunSanitize(label="Actualiser"))
                    if message is None:
                        return await self.message.reply(content, view=view, mention_author=False, silent=True)
                    else:
                        return await message.edit(content=content, view=view)
                elif message is None:
                    return await self.message.reply(
                        "C'est bien, tu as nettoyé tes liens",
                        silent=True,
                        mention_author=False,
                        delete_after=1
                    )
                else:
                    return await message.delete()
        return None


class SanitizeCog(MarinovCog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clean_sanitizer_db.start()

    @tasks.loop(time=utilitaires.minuit)
    async def clean_sanitizer_db(self):
        with RenderLink.renders as renders:
            for url, data in renders.items():
                # Supprime l'entrée si aucune URL n'est disponible
                if not data.get('available'):
                    del renders[url]
                    continue
                # Supprime les doublons dans la liste des entrées disponibles
                available = data['available']
                as_set, as_list = set(available), list(available)
                if len(as_set) != len(as_list):
                    renders[url]['available'] = list(as_set)
                # Définit une entrée par défaut si ce n'est pas fait
                if not data.get('default'):
                    renders[url]['default'] = available[0]
                # Ajoute l'entrée par défaut à la liste des entrées disponibles si ce n'est pas fait
                if not data['default'] in available:
                    renders[url]['available'] += [data['default']]
        with Sanitizer.exceptions as exceptions:
            for url, queries in exceptions.items():
                # Supprime l'entrée si aucune query n'est disponible
                if not queries:
                    del exceptions[url]
                    continue
                # Supprime les doublons dans la liste des queries
                as_set, as_list = set(queries), list(queries)
                if len(as_set) != len(as_list):
                    exceptions[url] = list(as_set)

    @commands.slash_command()
    async def render(self, ctx: discord.ApplicationContext, message: discord.Message, sanitized: discord.Message = None):
        sanitizer = Sanitizer(message)
        await ctx.response.send_modal(RenderLink(sanitizer.extract(), title="Rendu des liens"))
        await sanitizer.sanitize(sanitized)
