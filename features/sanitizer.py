from urllib.parse import urlsplit, SplitResult, parse_qs, parse_qsl, urlunsplit, urlencode

import discord
from discord.ext import commands, tasks

import utilitaires
from features import LulusCog
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
    def __init__(self, *args, **kwargs):
        kwargs['custom_id'] = kwargs.get('custom_id', 'rerun_sanitize')
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction):
        await Sanitizer.run(interaction.message)
        await interaction.respond('Analyse des liens terminée', ephemeral=True, delete_after=3)


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
        with SanitizeView.exceptions as exceptions:
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

    def __init__(self, urls, *args, sanitized_message: discord.Message = None, **kwargs):
        super().__init__(*args, **kwargs)
        index = -1
        self.sanitized_message = sanitized_message
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
                for link in renders.get(short_netloc(url.netloc), {}).get('available', [])
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
        await Sanitizer.run(self.sanitized_message or interaction.message)
        return await interaction.respond(f'Rendu ajouté pour {domain} : {new_domain or alternative}', ephemeral=True)


class SanitizeView(discord.ui.View):
    exceptions = Transaction(JsonStore(config.get('SANITIZER_WHITELIST', 'sanitize_whitelist.json')))

    def __init__(self, raw_urls: list[SplitResult], sanitizer, *args, **kwargs):
        super().__init__(*args, **kwargs)
        urls = raw_urls or []
        self.sanitizer = sanitizer
        self.url_content = ''
        self._queries = 0
        self._renders = 0
        if urls:
            with self.exceptions as exceptions:
                surls: list[SplitResult] = list(map(lambda u: self._sanitize(u, exceptions), urls))
            raw_surls = [surl._replace(netloc=short_netloc(surl.netloc)) for surl in surls]
            for i, surl in enumerate(surls):
                with RenderLink.renders as renders:
                    if has_render := (sn := short_netloc(surl.netloc)) in renders:
                        self._renders += 1
                        if (default := renders[sn].get('default')) is not None:
                            surl = surl._replace(netloc=default)
                if urlunsplit(surl) == urlunsplit(urls[i]):
                    if not has_render:
                        continue
                    self._queries += 1

                url = urlunsplit(surl)
                raw_surl = raw_surls[i]
                self.url_content += f"{url}\n"
                self.add_item(
                    discord.ui.Button(
                        url=urlunsplit(raw_surl),
                        label=''.join(
                            filter(
                                lambda s: s != 'www',
                                raw_surl.netloc.split('.')[:-1]
                            )
                        ),
                    )
                )
        if not self.sanitizer.url_only or self.has_queries:
            if self.has_queries:
                title = 'Ajouter des Exceptions'
                self.add_item(ButtonModal(AddException(AddException.valid_urls(urls), title=title), label=title))
            if self.has_renders:
                title = 'Rendu des liens'
                self.add_item(ButtonModal(RenderLink(urls, title=title), label=title))
            self.add_item(RerunSanitize(label="Actualiser"))

    @property
    def is_empty(self) -> bool:
        return not self.has_queries and not self.has_renders

    @property
    def has_queries(self) -> bool:
        return self._queries > 0

    @property
    def has_renders(self) -> bool:
        return self._renders > 0

    @property
    def content(self):
        if self.is_empty:
            return self.url_content
        built = 'Liens'
        if self.has_queries:
            built += ' sans trackers (potentiellement trop fort)'
            if self.has_renders:
                built += ' et'
        if self.has_renders:
            built += ' mieux rendus'
        return built + '\n' + self.url_content

    @staticmethod
    def _sanitize(url: SplitResult, exceptions: dict[str, list[str]]) -> SplitResult:
        allowed = exceptions.get(short_netloc(url.netloc), [])
        queries = {k: v for k, v in parse_qs(url.query).items() if k in allowed}
        return url._replace(query=urlencode(queries, doseq=True))

    async def on_timeout(self) -> None:
        await super().on_timeout()
        if hasattr(self, 'message'):
            try:
                await self.message.edit(
                    view=discord.ui.View(
                        *filter(
                            lambda child: hasattr(child, 'url') and child.url,
                            self.children
                        )
                    )
                )
            except discord.errors.NotFound:
                pass


class Sanitizer:
    WEBHOOK_NAME = '{bot_name} - Sanitizer'

    def __init__(self, message: discord.Message):
        self.message = message

    @property
    def url_only(self):
        urls = self.extract()
        return len(self.message.content.replace(' ', '')) == sum(map(len, map(SplitResult.geturl, urls)))

    def extract(self) -> list[SplitResult]:
        urls = list()
        for word in self.message.content.replace('\n', ' ').split(' '):
            url = urlsplit(word)
            if url.scheme and url.netloc:
                urls.append(url)
        return urls

    @staticmethod
    async def run(sanitized_message: discord.Message):
        try:
            source = await sanitized_message.channel.fetch_message(sanitized_message.reference.message_id)
            await Sanitizer(source).sanitize(message=sanitized_message)
        except Exception:
            await config.channel_logs.send(
                embed=Embed(
                    title="Sanitizer - rerun",
                    description=f"```python\n{fail().strip()}\n```",
                    color=0x00ff00
                )
            )

    @property
    async def webhook(self) -> discord.Webhook:
        webhook_name = self.WEBHOOK_NAME.format(bot_name=self.message.guild.me.display_name)
        for webhook in await self.message.channel.webhooks():
            if webhook.name == webhook_name and webhook.user.id == self.message.guild.me.id:
                return webhook
        return await self.message.channel.create_webhook(
            name=webhook_name,
            avatar=await self.message.guild.me.avatar.read(),
        )

    # Update le message passé en paramètre, ou en crée un nouveau
    async def sanitize(self, *, message: discord.Message = None) -> discord.Message | None:
        msg = None
        if not self.message.author.bot:
            if urls := self.extract():
                view = SanitizeView(urls, self)
                if not view.is_empty:
                    if message is None:
                        if self.url_only and not view.has_queries:
                            msg = await (await self.webhook).send(
                                content=view.url_content,
                                view=view,
                                username=self.message.author.display_name,
                                avatar_url=self.message.author.avatar.url,
                            )
                            await self.message.delete()
                        else:
                            msg = await self.message.reply(
                                content=view.content,
                                view=view,
                                mention_author=False,
                                silent=True
                            )
                    else:
                        msg = await message.edit(content=view.content, view=view)
                elif message is not None:
                    await message.delete()
                if msg:
                    setattr(view, 'message', msg)
        return msg


class SanitizeCog(LulusCog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.clean_sanitizer_db.start()

    @staticmethod
    async def on_message(message: discord.Message):
        await Sanitizer(message).sanitize()

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
        with SanitizeView.exceptions as exceptions:
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
    @discord.option(name="message", description="Message original à re-analyser")
    @discord.option(name="sanitized", description="Message produit à mettre à jour")
    async def render(self, ctx: discord.ApplicationContext, message: discord.Message,
                     sanitized: discord.Message = None):
        await ctx.response.send_modal(
            RenderLink(
                Sanitizer(message).extract(),
                sanitized_message=sanitized,
                title="Rendu des liens"
            )
        )
