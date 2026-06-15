import os

import discord
import dotenv


class Config:
    def __init__(self, env):
        self.values = {
            **dotenv.dotenv_values(env),
            **os.environ,
        }
        self.channel_logs: discord.Thread = None

    def __getitem__(self, item):
        return self.values[item]

    def get(self, item, default=None):
        return self.values.get(item, default)

    def set_log_channel(self, channel: discord.ChannelType):
        self.channel_logs = channel


config = Config('.env')
