#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import discord
from discord.ext import commands
from .utils.settings import load_settings
from dawcord import DawCord


def run():
    parser = argparse.ArgumentParser(
        description="Low latency DAW to Discord audio piping bot using Cockos' ReaStream"
    )
    parser.add_argument(
        "channelID",
        metavar="channelID",
        type=int,
        help="Discord channel ID to send audio to",
    )
    parser.add_argument(
        "--config",
        metavar="<path>",
        dest="config",
        default="config.json",
        help="Config file location (default 'config.json')",
    )
    args = parser.parse_args()

    # Load/create settings file
    config = load_settings(args.config)
    if config is None:
        print(
            f'Generated configuration file "{args.config}" in current directory.\nPlease fill in your bot token before running again.'
        )
        return

    # Setup global logging
    discord.utils.setup_logging(root=True)

    # Configure and run bot
    bot = DawCord(
        intents=discord.Intents.default(),
        command_prefix="%",
        channelid=int(args.channelID),
        ipaddr=config["ip"],
        port=config["port"],
        identifier=config["identifier"],
        resample_type=config["resample_quality"],
        gain=config["gain"],
    )
    # Run with token, and disable log handler (already configured root logger above)
    bot.run(config["token"], log_handler=None)


if __name__ == "__main__":
    run()
