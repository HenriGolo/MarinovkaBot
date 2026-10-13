import re

import discord
from discord.ext import commands

from features import BaseAutoAddedCog
from utilitaires import Embed
from utilitaires.decorateurs import logger

tonetags = {
    '/a': 'affectueusement',
    '/c': 'copypasta',
    '/cb': 'clickbait',
    '/f': 'faux',
    '/gen': 'sincèrement',
    '/g': 'sincèrement',
    '/genq': 'question sincère',
    '/hj': 'demi-blague',
    '/hyp': 'hyperbole',
    '/ij': 'inside joke',
    '/j': 'blague',
    '/l': 'paroles',
    '/ly': 'paroles',
    '/lh': 'avec légèreté',
    '/li': 'littéralement',
    '/lu': 'un peu agacé',
    '/m': 'métaphore',
    '/nav': 'pas un vent',
    '/nbh': 'personne ici',
    '/neg': 'connotation négative',
    '/ng': 'connotation négative',
    '/neu': 'connotation neutre',
    '/nf': 'pas obligatoire',
    '/nm': 'pas en colère',
    '/npa': 'pas passif-agressif',
    '/nsb': 'sans subtweeting',
    '/nsrs': 'pas sérieusement',
    '/nsx': 'sans intention sexuelle',
    '/nx': 'sans intention sexuelle',
    '/p': 'platonique',
    '/pa': 'passif-agressif',
    '/pos': 'connotation positive',
    '/pc': 'connotation positive',
    '/q': 'citation',
    '/r': 'romantique',
    '/ref': 'référence',
    '/rh': 'rhétorique',
    '/rt': 'rhétorique',
    '/s': 'sarcastique',
    '/srs': 'sérieusement',
    '/sx': 'sexuel',
    '/x': 'sexuel',
    '/t': 'en taquinant',
    '/th': 'menace'
}


class ToneTags(BaseAutoAddedCog):
    @commands.message_command(name='Tonetag(s)')
    @logger
    async def tonetag_msg(self, ctx: discord.ApplicationContext, message: discord.Message):
        await ctx.defer(ephemeral=True)
        comp = re.compile(r"(?<!\w)(?P<tag>" + "|".join(re.escape(tag) for tag in tonetags.keys()) + r")(?!\w)")
        if not (found := set(comp.findall(message.content))):
            await ctx.respond("Aucun tonetag trouvé dans le message.")
            return
        description = "\n".join(f"{tag} : {tonetags[tag]}" for tag in found)
        embed = Embed(title="Tonetag(s) trouvé(s)", description=description, color=ctx.user.color)
        await ctx.respond(embed=embed)

    @commands.slash_command(name='tonetag')
    async def tonetag_slash(self, ctx: discord.ApplicationContext, message: discord.Message):
        return await ctx.invoke(self.tonetag_msg, message=message)
