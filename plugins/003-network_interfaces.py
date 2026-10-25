#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Snapshot network interfaces without sending packets."""

import json
from pathlib import Path

from loader.plugin_helpers import read_text, result


PLUGIN = {
    'id': 'RP003',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'Network interface inventory',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'Network',
    'requires': ['network'],
    'timeout_s': 5,
    'documentation': {
        'title': '网络接口清单',
        'criterion': '记录非 loopback 接口，结果待人工复核。',
    },
}


NET_ROOT = Path('/sys/class/net')


def probe(root=NET_ROOT):
    interfaces = []
    for path in sorted(root.iterdir()) if root.is_dir() else []:
        if path.name == 'lo':
            continue
        interfaces.append({'name': path.name, 'operstate': read_text(path / 'operstate'),
                           'carrier': read_text(path / 'carrier'),
                           'address': read_text(path / 'address')})
    if not interfaces:
        return result('skip', 'No non-loopback network interfaces found')
    return result('needs_review', f'{len(interfaces)} network interface(s) observed',
                  value=len(interfaces), unit='interfaces', details={'interfaces': interfaces})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
