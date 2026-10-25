#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Select the systemd boot target."""

import json
import os
from pathlib import Path
import subprocess

from loader.plugin_helpers import plugin_params, result


PLUGIN = {
    'id': 'RP037',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Boot target',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'System',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change the default boot target? A reboot is required.',
    'inputs': [
        {
            'name': 'target',
            'label': 'Boot target',
            'type': 'choice',
            'choices': ['console', 'desktop'],
            'required': True,
        },
    ],
    'timeout_s': 10,
    'documentation': {
        'title': '启动目标',
        'criterion': '选择终端或桌面，重启后生效。',
    },
}


def probe(target, run=subprocess.run):
    if target not in ('console', 'desktop'):
        return result('error', 'Invalid boot target')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    if target == 'desktop' and not Path('/etc/init.d/lightdm').exists():
        return result('skip', 'Desktop target requires LightDM')
    unit = 'graphical.target' if target == 'desktop' else 'multi-user.target'
    try:
        completed = run(['systemctl', 'set-default', unit],
                        capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass' if completed.returncode == 0 else 'fail',
                  f'Default target {unit}; reboot required' if completed.returncode == 0 else
                  f'Could not set default target {unit}',
                  details={'stderr': completed.stderr[-1000:]})


if __name__ == '__main__':
    print(json.dumps(probe(plugin_params()['target']), ensure_ascii=False))
