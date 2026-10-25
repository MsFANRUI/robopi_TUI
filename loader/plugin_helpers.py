# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Shared parameter, result, file-reading and file-writing helpers for plugins."""

import argparse
import json
import os
from pathlib import Path
import sys
import tempfile


def plugin_params():
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--params')
    source.add_argument('--params-stdin', action='store_true')
    args = parser.parse_args()
    values = json.loads(sys.stdin.read() if args.params_stdin else args.params)
    if not isinstance(values, dict):
        parser.error('Plugin parameters must be a JSON object')
    return values


def read_text(path):
    try:
        return Path(path).read_text(errors='replace').strip('\x00\n ')
    except OSError:
        return ''


def result(status, message, *, value=None, unit=None, details=None):
    return {'status': status, 'value': value, 'unit': unit,
            'message': message, 'details': details or {}}


def atomic_write(path, content):
    """Replace a configuration file while preserving its owner and mode."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    stat = path.stat() if path.exists() else None
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.' + path.name + '.', delete=False) as stream:
            name = stream.name
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, stat.st_mode & 0o777 if stat else 0o644)
        if stat:
            os.chown(name, stat.st_uid, stat.st_gid)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


