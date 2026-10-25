#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Check WS2812 light-board prerequisites without changing LED output."""

import json
from pathlib import Path
import shutil

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP016',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'Light board readiness',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'Addon',
    'requires': [],
    'timeout_s': 5,
    'documentation': {
        'title': '灯板就绪状态',
        'criterion': 'WS2812 字符设备与工具齐备仍待人工复核，需要目视确认。',
    },
}


DEVICE = Path('/dev/robopi-ws2812')


def probe(device=DEVICE, command=None):
    if command is None:
        command = shutil.which('robopi-ws2812')
    device_present = device.is_char_device()
    details = {'device': str(device), 'device_present': device_present,
               'command': command}
    if not command and not device_present:
        return result('skip', 'Light-board driver and tool are not installed', details=details)
    if not command or not device_present:
        return result('fail', 'Light-board driver or tool is missing', details=details)
    return result('needs_review', 'Driver and tool present; LED output needs visual confirmation',
                  details=details)


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
