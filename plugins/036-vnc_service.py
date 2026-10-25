#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Control an installed WayVNC or RealVNC service."""

import json
import os
from pathlib import Path
import subprocess

from loader.plugin_helpers import plugin_params, result


PLUGIN = {
    'id': 'RP036',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'VNC service control',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Interfaces',
    'batch': False,
    'safety': 'active',
    'confirm': 'Changing VNC may disconnect a remote desktop. Continue?',
    'inputs': [
        {
            'name': 'operation',
            'label': 'Operation',
            'type': 'choice',
            'choices': ['enable', 'disable'],
            'required': True,
        },
        {
            'name': 'service',
            'label': 'VNC implementation',
            'type': 'choice',
            'choices': ['wayvnc.service', 'vncserver-x11-serviced.service'],
            'required': True,
        },
    ],
    'timeout_s': 20,
    'documentation': {
        'title': 'VNC 服务',
        'criterion': '在已安装的 VNC 服务中选择并启停。',
    },
}


def probe(operation, service, run=subprocess.run):
    if operation not in ('enable', 'disable') or service not in PLUGIN['inputs'][1]['choices']:
        return result('error', 'Invalid VNC operation or service')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    if not any((directory / service).is_file() for directory in (
            Path('/usr/lib/systemd/system'), Path('/lib/systemd/system'),
            Path('/etc/systemd/system'))):
        return result('skip', f'{service} is not installed')
    try:
        completed = run(['systemctl', operation, '--now', service],
                        capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass' if completed.returncode == 0 else 'fail',
                  f'{service}: {operation} exit {completed.returncode}',
                  details={'stderr': completed.stderr[-1000:]})


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
