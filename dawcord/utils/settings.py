# -*- coding: utf-8 -*-

import json
from pathlib import Path


def load_settings(filename):
    # Read settings from json config file
    path = Path(filename)
    settings = dict()
    if path.is_file():
        return read_json(path)

    # If file does not exist, create it with default values
    settings = {
        "token": "",
        "source": "reastream",
        "encoder": {
            "application": "audio",
            "bitrate": 128,
            "fec": True,
            "expected_packet_loss": 0.15,
            "bandwidth": "full",
            "signal_type": "music",
        },
        "source.reastream": {
            "ip": "127.0.0.1",
            "port": 58710,
            "identifier": "default",
            "timeout": 2.0,
            "resample_quality": "VHQ",
            "max_buffer_frames": 8,
            "playback_slack_frames": 2,
            "gain": -3,
        },
        "source.pyaudio": {
            "device_name": "",
            "timeout": 2.0,
            "max_buffer_frames": 8,
            "playback_slack_frames": 2,
            "gain": 0,
        },
    }
    write_json(path, settings)
    return None


def read_json(file):
    with open(file, "rt") as f:
        return json.load(f)


def write_json(file, data):
    with open(file, "wt") as f:
        json.dump(data, f, indent=4)
