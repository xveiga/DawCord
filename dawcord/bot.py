#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import discord
from .utils.settings import load_settings
from .dawcord import DawCord


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
    parser.add_argument(
        "--token",
        metavar="<token>",
        dest="token",
        default=None,
        help="Discord API token",
    )
    args = parser.parse_args()

    # Load/create settings file
    config = load_settings(args.config)
    if config is None:
        print(
            f'Generated configuration file "{args.config}" in current directory.\nPlease fill in your bot token before running again.'
        )
        return

    # Fetch Discord API token
    env_token = os.environ.get("TOKEN")
    if args.token is not None:
        # Retrieve token from args if available
        token = args.token
    elif env_token is not None:
        # Otherwise, try from environment variable
        token = env_token
    else:
        # Finally, fallback to config file
        token = config.get("token")
    if token is None:
        print(
            "Could not read Discord API token neither from environment variable, nor arguments, nor config file",
            file=sys.stderr,
        )
        return

    # Setup global logging
    discord.utils.setup_logging(root=True)

    # Configure and run bot
    bot = DawCord(
        intents=discord.Intents.default(),
        command_prefix="%",
        channelid=int(args.channelID),
        config=config,
    )

    # Run with token, and disable log handler (already configured root logger above)
    bot.run(token, log_handler=None)


if __name__ == "__main__":
    run()
