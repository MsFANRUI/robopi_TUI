#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Persist NetworkManager Wi-Fi power-save policy."""

import json
import os
from pathlib import Path
import subprocess

from loader.plugin_helpers import atomic_write, plugin_params, result

PLUGIN = {
    'id': 'RP047',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Wi-Fi power saving',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Network',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change Wi-Fi power saving? The radio may reconnect.',
    'inputs': [
        {
            'name': 'operation',
            'label': 'Power saving',
            'type': 'choice',
            'choices': ['enable', 'disable'],
            'required': True,
        },
    ],
    'timeout_s': 10,
    'documentation': {
        'title': 'Wi-Fi 省电',
        'criterion': '修改 NetworkManager 配置并重新加载。',
    },
}


def probe(operation, path=Path('/etc/NetworkManager/conf.d/default-wifi-powersave-off.conf'),
          run=subprocess.run):
    if operation not in ('enable', 'disable'):
        return result('error', 'Invalid Wi-Fi power-save operation')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        if operation == 'disable':
            atomic_write(path, '[connection]\nwifi.powersave = 2\n')
        else:
            path.unlink(missing_ok=True)
        reloaded = run(['systemctl', 'reload', 'NetworkManager'], capture_output=True,
                       text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass' if reloaded.returncode == 0 else 'needs_review',
                  f'Wi-Fi power saving {operation}d; NetworkManager reload '
                  f'exit {reloaded.returncode}')


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
