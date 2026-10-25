#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Read the board serial number from device tree or procfs."""

import json
from pathlib import Path
import re

from loader.plugin_helpers import read_text, result


PLUGIN = {
    'id': 'RP034',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'Board serial number',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'test',
    'category': 'System',
    'safety': 'passive',
    'timeout_s': 5,
    'documentation': {
        'title': '板卡序列号',
        'criterion': '只读设备树或 CPU 信息。',
    },
}


def probe(tree=Path('/proc/device-tree/serial-number'), cpuinfo=Path('/proc/cpuinfo')):
    serial = read_text(tree)
    if not serial:
        match = re.search(r'(?im)^Serial\s*:\s*(\S+)', read_text(cpuinfo))
        serial = match.group(1) if match else ''
    if not serial:
        return result('skip', 'Board serial number not available')
    return result('pass', f'Board serial number: {serial}', details={'serial': serial})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
