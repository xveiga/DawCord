=======
DawCord
=======

Low-latency DAW to *Discord* audio piping bot using [*Cockos' ReaStream*](https://www.reaper.fm/reaplugs/)

Created to solve the latency problems of sharing your DAW screen (and audio) on
Discord with a Windows machine. Uses a Discord Bot account to transmit audio
directly from a ReaStream instance, on software that supports VST plugin effects
(Reaper, Cubase, Ableton, FL Studio, Deckadance, Adobe Audition, Premiere, and more...).
Can also be used to stream an audio source from Open Broadcaster Software.

Made using [*discord.py*](https://github.com/Rapptz/discord.py)

Installation and Usage
======================
Steps for running locally (DAW and bot on same machine):

1. Install *python 3.9* or newer. If you have *pip* available you can run ``python -m pip install git+https://github.com/xveiga/dawcord.git@main``.
#. Install ReaStream (https://www.reaper.fm/reaplugs/) and configure your DAW to find the plugin correctly.
#. Run the bot once with ``dawcord 0``.
#. Go to the Discord Developer Portal, create a bot, and get an OAuth2 token.
#. Paste the token on the *config.json* file.
#. Enable *Developer Options* in Discord client, go to the channel you want the bot to join and click *Copy ID*.
#. Launch your DAW, configure the sample rate to **48000Hz** and place ReaStream on the audio track/source you want to stream to Discord. Other sample rates are **not** supported yet.
#. Choose *Send audio/MIDI*, then select *local broadcast*, leave identifier as *default*.
#. Run the bot again with ``dawcord <channelID>``, replacing ``<channelID>`` with the ID you copied on step 4.
#. Enjoy! For subsequent runs only steps 7 to 9 are needed.
#. Stop the bot with *Control+C*, or by disconnecting it manually from the channel.

Notes / Known issues
====================
- Only supports 48kHz sample rate. No decimation or interpolation is implemented.
- Bitrate is hardcoded on discord.py to 160kbps, independendly of the channel
  configuration. Quality is pretty good to show something quickly, but not for
  any serious work (sound is muddier, middle frequencies are boosted slightly,
  highs lose detail compared to source). On discord's mobile apps, the audio is
  compressed further, and converted to mono.
- Audio may lag back/accelerate or even stop working if DAW glitches (CPU usage
  too high, loading plugins or changing sound card parameters). Discord.py's
  opus encoder may get confused by this, as it's designed for "static", readily
  available, buffered sources. Just restart the bot and it should work again.
- If buffer accumulates too much slack time (adding to latency and memory usage),
  there's currently no mechanism to flush it other than a restart.
- Voice client is not stopped when UDP packets stop, but the opus encoder and
  discord seem to work properly with "emptiness" anyway.
- On Windows platforms, asyncio throws a "RuntimeError: Event loop is closed",
  this is a problem with the upstream implementation. There's a workaround which
  adds delay on closing, making the bot seem unresponsive, so i've decided to
  keep it as is.
- Do not add more than one source with the same identifier broadcasting on the
  same broadcast domain, as it will result in "interlaced" choppy audio. If you
  need more than one source for other uses, change the *default* identifier in
  the *config.json* file.
- With separate bot accounts, you can run multiple instances. Just pass the
  command line option ``--config`` to specify a different config file and have
  indepentent settings for each one.