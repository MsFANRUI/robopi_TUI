#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Check the configured RoboParty public APT source and its InRelease file."""

import json
import subprocess
from urllib.parse import urlparse
from urllib.request import urlopen

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP004',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'RoboParty APT repository',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'Network',
    'requires': ['apt'],
    'timeout_s': 15,
    'documentation': {
        'title': 'RoboParty APT 源',
        'criterion': '已配置 `apt.roboparty.com`，`common/InRelease` 可访问并有 PGP 签名消息头；不单独验证签名。',
    },
}


HOST = 'apt.roboparty.com'
INRELEASE = 'https://apt.roboparty.com/dists/common/InRelease'


def configured_uris():
    completed = subprocess.run(['apt-get', 'indextargets', '--format', '$(URI)'],
                               capture_output=True, text=True, timeout=3, check=True)
    return completed.stdout.splitlines()


def fetch_inrelease(url):
    with urlopen(url, timeout=6) as response:
        return response.read(128)


def probe(indexes=configured_uris, fetch=fetch_inrelease):
    try:
        uris = indexes()
        configured = [uri for uri in uris if urlparse(uri).hostname == HOST]
        if not configured:
            return result('fail', f'{HOST} is not configured as an APT source')
        header = fetch(INRELEASE)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return result('fail', f'Could not reach {HOST}: {exc}')
    if not header.startswith(b'-----BEGIN PGP SIGNED MESSAGE-----'):
        return result('fail', f'{HOST} returned an invalid InRelease header')
    return result('pass', f'{HOST} InRelease is reachable',
                  details={'inrelease': INRELEASE, 'configured_indexes': configured[:12]})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
