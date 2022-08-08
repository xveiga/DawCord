#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
from discord.ext import commands
from .utils.settings import load_settings
from .dawcord import DawCord

# import asyncio
# import platform


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

    # "Event loop is closed" asyncio workaround for Windows (adds delay on close, SIGTERM)
    # if platform.system() == "Windows":
    #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Load/create settings file
    config = load_settings(args.config)
    if config is None:
        print(
            f'Generated configuration file "{args.config}" in current directory.\nPlease fill in your bot token before running again.'
        )
        return

    # Configure and run bot
    bot = DawCord(
        command_prefix="%",
        channelid=int(args.channelID),
        ipaddr=config["ip"],
        port=config["port"],
        identifier=config["identifier"],
    )
    bot.run(config["token"])


if __name__ == "__main__":
    run()
