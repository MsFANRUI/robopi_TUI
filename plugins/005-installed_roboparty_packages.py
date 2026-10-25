#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""List installed RoboParty packages and their versions."""

import json
import subprocess

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP005',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'Installed RoboParty packages',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'System',
    'requires': [],
    'timeout_s': 10,
    'documentation': {
        'title': '已安装 RoboParty 包',
        'criterion': '列出 `roboparty-*`、`robopi-*` 包，且包含 `roboparty-base`。',
    },
}


def probe(query=None):
    if query is None:
        query = lambda: subprocess.run(
            ['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\t${Status}\n'],
            capture_output=True, text=True, timeout=5, check=False)
    try:
        completed = query()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', f'Could not list installed packages: {exc}')
    if completed.returncode:
        return result('error', 'dpkg-query failed',
                      details={'diagnostic': completed.stderr.strip()[:300]})
    packages = []
    for line in completed.stdout.splitlines():
        parts = line.split('\t')
        if len(parts) == 3 and parts[2] == 'install ok installed':
            name = parts[0].split(':', 1)[0]
            if name.startswith(('roboparty-', 'robopi-')):
                packages.append({'name': name, 'version': parts[1]})
    packages.sort(key=lambda item: item['name'])
    names = {item['name'] for item in packages}
    return result('pass' if 'roboparty-base' in names else 'fail',
                  f'{len(packages)} RoboParty package(s) installed',
                  value=len(packages), unit='packages',
                  details={'packages': packages, 'required': 'roboparty-base'})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
