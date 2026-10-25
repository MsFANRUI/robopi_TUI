#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Read DRM connector state and advertised modes."""

import json
from pathlib import Path

from loader.plugin_helpers import read_text, result


PLUGIN = {
    'id': 'RP033',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'Display connector inventory',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'test',
    'category': 'Display',
    'safety': 'passive',
    'requires': ['drm'],
    'timeout_s': 5,
    'documentation': {
        'title': 'DRM 连接与模式',
        'criterion': '只读连接状态与支持的分辨率。',
    },
}


def probe(root=Path('/sys/class/drm')):
    connectors = []
    for path in sorted(root.glob('card*-*/status')):
        connectors.append({'name': path.parent.name, 'status': read_text(path),
                           'modes': read_text(path.parent / 'modes').splitlines()[:32]})
    if not connectors:
        return result('skip', 'No DRM connectors found')
    return result('needs_review', f'{len(connectors)} display connector(s) found',
                  value=len(connectors), unit='connectors',
                  details={'connectors': connectors})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
