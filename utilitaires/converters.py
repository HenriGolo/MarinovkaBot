import re
from enum import Enum

from discord.ext.commands import Converter, Context
from discord.ext.commands.converter import T_co


class TextColor(Enum):
    gray = 30
    red = 31
    green = 32
    yellow = 33
    blue = 34
    pink = 35
    cyan = 36
    white = 37


class BackgroundColor(Enum):
    firefly_darj_blue = 40
    orange = 41
    marble_blue = 42
    greyish_turquoise = 43
    gray = 44
    indigo = 45
    light_gray = 46
    white = 47


class ANSI(Converter):
    """
    Coloration ANSI facilitée par des balises
    """
    @classmethod
    def converter(cls, argument: str) -> str:
        if not argument.strip():
            return argument

        colors = {f"<{c.name}>": f"\u001b[{c.value}m" for c in TextColor}
        colors["<reset>"] = f"\u001b[0m"
        bgcolors = {f"<bg_{c.name}>": f"\u001b[{c.value}m" for c in BackgroundColor}
        tags = re.compile(r"<[a-z_]+>")  # Pas le filtrage le plus optimal
        found = re.findall(tags, argument)
        if not found:
            return argument

        parts = argument.split("```")
        parts[1::2] = [f"```{e}```" for e in parts[1::2]]
        modified = list()
        for part in parts[::2]:
            part = part.strip()
            need_wrap = False
            for pattern in re.findall(tags, part):
                if pattern in colors:
                    part = part.replace(pattern, colors[pattern])
                    need_wrap = True
                if pattern in bgcolors:
                    part = part.replace(pattern, bgcolors[pattern])
                    need_wrap = True
            if not part:  # str vide
                need_wrap = False
            if need_wrap:
                part = f"```ansi\n{part}\n```"
            modified.append(part)
        parts[::2] = modified
        return "\n".join(parts)

    async def convert(self, ctx: Context, argument: str) -> T_co:
        return self.converter(argument)
