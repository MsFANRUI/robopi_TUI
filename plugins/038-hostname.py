#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Set a validated board hostname."""

import json
import os
import re
import subprocess

from loader.plugin_helpers import plugin_params, result


PLUGIN = {
    'id': 'RP038',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Board hostname',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'System',
    'batch': False,
    'safety': 'active',
    'confirm': 'Changing the hostname may affect network discovery. Continue?',
    'inputs': [
        {
            'name': 'hostname',
            'label': 'New hostname',
            'type': 'text',
            'pattern': '[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?',
            'required': True,
        },
    ],
    'timeout_s': 10,
    'documentation': {
        'title': '主机名',
        'criterion': '使用 hostnamectl。',
    },
}


def probe(hostname, run=subprocess.run):
    if not isinstance(hostname, str) or not re.fullmatch(
            r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', hostname):
        return result('error', 'Invalid hostname')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        completed = run(['hostnamectl', 'set-hostname', hostname],
                        capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass' if completed.returncode == 0 else 'fail',
                  f'Hostname set to {hostname}' if completed.returncode == 0 else
                  'Hostname update failed',
                  details={'stderr': completed.stderr[-1000:]})


if __name__ == '__main__':
    print(json.dumps(probe(plugin_params()['hostname']), ensure_ascii=False))
