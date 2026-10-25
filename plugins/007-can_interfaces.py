#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Inspect CAN links; never bring interfaces up or transmit frames."""

import json
from pathlib import Path
import re
import subprocess

from loader.plugin_helpers import read_text, result


PLUGIN = {
    'id': 'RP007',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'CAN interface inventory',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'Interfaces',
    'requires': ['can'],
    'timeout_s': 15,
    'documentation': {
        'title': 'CAN 接口清单',
        'criterion': '记录 `canN` 状态，待人工复核；不发送 CAN 帧。',
    },
}


NET_ROOT = Path('/sys/class/net')


def link_details(name):
    try:
        completed = subprocess.run(['ip', '-j', '-details', '-statistics', 'link',
                                    'show', 'dev', name], capture_output=True, text=True,
                                   timeout=2, check=False)
        if completed.returncode:
            return {'query_error': completed.stderr.strip()[:200]}
        items = json.loads(completed.stdout)
        if not items:
            return {}
        link = items[0]
        can = (link.get('linkinfo') or {}).get('info_data') or {}
        timing = can.get('bittiming') or {}
        return {'can_state': can.get('state'), 'bitrate': timing.get('bitrate'),
                'restart_ms': can.get('restart_ms'), 'statistics': link.get('stats64', {})}
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {'query_error': str(exc)[:200]}


def probe(root=NET_ROOT, query=link_details):
    interfaces = []
    for path in sorted(root.glob('can[0-9]*')):
        if not re.fullmatch(r'can[0-9]+', path.name):
            continue
        interfaces.append({'name': path.name, 'operstate': read_text(path / 'operstate'),
                           'mtu': read_text(path / 'mtu'), **query(path.name)})
    if not interfaces:
        return result('skip', 'No CAN interfaces found')
    return result('needs_review', f'{len(interfaces)} CAN interface(s) observed; no frame sent',
                  value=len(interfaces), unit='interfaces',
                  details={'interfaces': interfaces})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
