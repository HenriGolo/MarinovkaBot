import os
import sys

import discord
import dotenv


class Config:
    def __init__(self, envs):
        self.values = {
            **{
                k: v
                for env in envs
                for k, v in dotenv.dotenv_values(env).items()
            },
            **os.environ,
        }
        self.channel_logs: discord.Thread = None
        self.json_format = {}

    def __getitem__(self, item):
        return self.values[item]

    def get(self, item, default=None):
        return self.values.get(item, default)

    def set_log_channel(self, channel: discord.ChannelType):
        self.channel_logs = channel


config = Config(sys.argv[1:] if len(sys.argv) > 1 else ['.env'])
