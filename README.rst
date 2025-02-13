=======
DawCord
=======

Low-latency DAW to *Discord* audio piping bot using [*Cockos' ReaStream*](https://www.reaper.fm/reaplugs/)

Created to solve the latency problems of sharing your DAW screen (and audio) on
Discord with a Windows machine. Uses a Discord Bot account to transmit audio
directly from a ReaStream instance, on software that supports VST plugin effects
(Reaper, Cubase, Ableton, FL Studio, Deckadance, Adobe Audition, Premiere, Open Broadcaster Software, and more...).
Can transmit audio from a Windows capture or playback audio device using the [*PyAudioWPatch*](https://github.com/s0d3s/PyAudioWPatch) fork

Made using [*discord.py*](https://github.com/Rapptz/discord.py)

Installation and Usage
======================
Steps for running locally (DAW and bot on same machine):

1. Install *Python 3.9* or newer. If you have *pip* available you can run ``python -m pip install git+https://github.com/xveiga/dawcord.git@main``.
2. Install ReaStream (https://www.reaper.fm/reaplugs/) and configure your DAW to find the plugin correctly.
3. Run the bot once with ``dawcord 0`` in order to create a template `config.json` file.
4. Go to the [*Discord Developer Portal*](https://discord.com/developers/applications), and create a new application.
5. Go to the *Bot* section, and add a new bot. Click on *Reset token*, confirm, and copy it for later.
6. Go to the *URL Generator* on the *OAuth2* section, select *Bot* scope, then generate an invite link with *Connect* and *Voice* permissions (it will look something like ``https://discord.com/api/oauth2/authorize?client_id=<your bot's ID>&permissions=3145728&scope=bot``.
7. Copy and paste the authorization URL on your browser, and invite the bot to the server you want.
8. Paste the bot token on the *config.json* file.
9. Enable *Developer Options* in Discord client, go to the channel you want the bot to join and click *Copy ID*.

If you want to send sound from your DAW directly:

10. Launch your DAW, place *ReaStream* on the audio track/source you want to stream to Discord.
#. Choose *Send audio/MIDI*, then select *local broadcast*, leave identifier as *default*.
#. Run the bot again with ``dawcord <channelID>``, replacing ``<channelID>`` with the ID you copied on step 4.
#. Enjoy! For subsequent runs only steps 10 to 12 are needed.
#. Stop the bot with *Control+C*, or by disconnecting it manually from the channel.

If you want to send sound from a Windows input or output device directly (for example, output of your sound card):

10. Edit the *config.json* file, and modify the ``source`` parameter from ``reastream`` to ``pyaudio``
#. Paste the Windows device name on the key subkey ``device_name`` located under ``source.pyaudio``. If you're unsure, running the bot will print the list of available devices.
#. Run the bot with ``dawcord <channelID>``, replacing ``<channelID>`` with the ID you copied on step 4.
#. Enjoy! For subsequent runs only step 13 is required.
#. Stop the bot with *Control+C*, or by disconnecting it manually from the channel.

Notes / Known issues
====================
- Do not add more than one source with the same identifier broadcasting on the
  same domain, as it will result in "interlaced" choppy audio. If you need more
  than one source for other uses, change the *default* identifier in the
  *config.json* file.
- With separate bot accounts, you can run multiple instances. Just pass the
  command line option ``--config`` to specify a different config file and have
  indepentent settings for each one.
- On Discord's mobile apps the audio is compressed further, and converted to mono.
  This is done on their servers and nothing can be done via the API to improve quality.
- Audio may lag back/accelerate or even stop working if DAW glitches (CPU usage
  too high, loading plugins or changing sound card parameters). Discord.py's player
  uses a fixed timer interval to read frames, which is designed for recorded
  sources, and does not account for any slack. The solution for now is to just restart the bot.