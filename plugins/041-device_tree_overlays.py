#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Inspect or set RoboPi device-tree overlays in the Armbian boot config."""

import json
import os
from pathlib import Path
import re

from loader.plugin_helpers import atomic_write, plugin_params, result

PLUGIN = {
    'id': 'RP041',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Device-tree overlays',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Interfaces',
    'batch': False,
    'safety': 'active',
    'confirm': 'Write the selected overlays to Armbian boot config? Reboot required.',
    'inputs': [
        {
            'name': 'operation',
            'label': 'Operation',
            'type': 'choice',
            'choices': ['inspect', 'set'],
            'required': True,
        },
        {
            'name': 'overlays',
            'label': 'Space-separated overlay names (empty disables all)',
            'type': 'text',
            'pattern': '[a-zA-Z0-9_ -]{0,512}',
            'when': {'operation': 'set'},
        },
    ],
    'timeout_s': 10,
    'documentation': {
        'title': '设备树 Overlay',
        'criterion': '只允许已安装的 DTBO 名称。',
    },
}


def settings(text):
    found = {}
    for line in text.splitlines():
        match = re.fullmatch(r'\s*(overlay_prefix|overlays)\s*=\s*(.*?)\s*', line)
        if match:
            found[match[1]] = match[2]
    return found


def available_overlays(directory, prefix):
    entries = {}
    for path in directory.glob('*.dtbo'):
        name = path.stem
        if prefix and name.startswith(prefix):
            name = name[len(prefix):].lstrip('-_')
        elif prefix:
            continue
        entries[name] = path.name
    return entries


BOOT_CONFIGS = ('/boot/orangepiEnv.txt', '/boot/armbianEnv.txt', '/boot/robopartyEnv.txt')
OVERLAY_DIRS = ('/boot/dtb/allwinner/overlay', '/boot/dtb/rockchip/overlay',
                '/boot/dtb/amlogic/overlay', '/boot/dtb/sunxi/overlay', '/boot/dtb/overlay')


def probe(operation, overlays='', config=None, directory=None):
    config = config or next((Path(p) for p in BOOT_CONFIGS if Path(p).is_file()), None)
    directory = directory or next((Path(p) for p in OVERLAY_DIRS if Path(p).is_dir()), None)
    if config is None or directory is None:
        return result('skip', 'Boot config or overlay directory is missing')
    try:
        original = config.read_text()
        current = settings(original)
        choices = available_overlays(directory, current.get('overlay_prefix', ''))
        details = {'configured': current.get('overlays', '').split(), 'available': choices}
        if operation == 'inspect':
            return result('pass', 'Overlay configuration captured', details=details)
        if operation != 'set' or not re.fullmatch(r'[a-zA-Z0-9_ -]{0,512}', overlays):
            return result('error', 'Invalid overlay operation or list')
        if os.geteuid() != 0:
            return result('fail', 'Root privileges required')
        selected = overlays.split()
        if len(selected) != len(set(selected)) or any(name not in choices for name in selected):
            return result('fail', 'Select each available overlay at most once', details=details)
        lines = original.splitlines(keepends=True)
        lines = [line for line in lines if not re.match(r'^\s*overlays\s*=', line)]
        lines.append('overlays=' + ' '.join(selected) + '\n')
        atomic_write(config, ''.join(lines))
    except OSError as exc:
        return result('error', str(exc))
    return result('pass', 'Overlays saved; reboot required', details={'selected': selected})


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
