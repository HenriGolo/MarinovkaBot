from functools import wraps

from .config import config
from utilitaires import fail, Embed, now
from utilitaires.converters import ANSI


def logger(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start = now(True)
        args_repr = [f"<cyan>{a!r}<reset>" for a in args]
        kwargs_repr = [f"{k}=<cyan>{v!r}<reset>" for k, v in kwargs.items()]
        signature = "\n\t".join(args_repr + kwargs_repr)

        try:
            result = await func(*args, **kwargs)

        except Exception:
            err = fail()
            embed = Embed(title=func.__name__, color=0xff0000)
            embed.description = f"```python\n{err.strip()}\n```"
            await config.channel_logs.send(embed=embed)

        else:  # Sera exécuté si aucune exception n'est soulevée
            embed = Embed(title=func.__name__, color=0x00ff00)
            embed.description = (
                f"<yellow>{args[0].__class__.__name__}.{func.__name__}<reset> avec comme arguments\n"
                f"\t{signature}\n"
            )
            embed.description = ANSI.converter(embed.description)
            embed.add_field(name="Durée", value=f"{(now(True) - start).total_seconds()}s")
            await config.channel_logs.send(embed=embed)
            return result

    return wrapper


def apply_list(decorators):
    """
    Applique une liste de décorateurs et renvoie la fonction décorée
    """

    def wrapper(func):
        for deco in reversed(decorators):
            func = deco(func)
        return func

    return wrapper
