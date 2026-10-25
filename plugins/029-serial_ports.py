#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Inventory serial devices and current line settings."""

import json
from pathlib import Path
import re

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP029',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'Serial port inventory',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'test',
    'category': 'Serial',
    'safety': 'passive',
    'requires': ['serial'],
    'timeout_s': 15,
    'documentation': {
        'title': '串口清单',
        'criterion': '仅列设备节点，不打开串口。',
    },
}


def probe(root=Path('/dev')):
    names = sorted(path.name for path in root.iterdir()
                   if re.fullmatch(r'tty(?:S|AMA|USB|ACM)[0-9]+', path.name))
    if not names:
        return result('skip', 'No serial devices found')
    return result('needs_review', f'{len(names)} serial port(s) found',
                  value=len(names), unit='ports', details={'ports': names})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
