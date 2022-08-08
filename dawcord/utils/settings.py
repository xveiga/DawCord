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
    settings = {"token": "", "ip": "127.0.0.1", "port": 58710, "identifier": "default"}
    write_json(path, settings)
    return None


def read_json(file):
    with open(file, "rt") as f:
        return json.load(f)


def write_json(file, data):
    with open(file, "wt") as f:
        json.dump(data, f, indent=4)
