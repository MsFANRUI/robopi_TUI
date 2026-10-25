#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Set a timezone after checking the installed zoneinfo database."""

import json
import os
from pathlib import Path
import re
import subprocess

from loader.plugin_helpers import plugin_params, result


PLUGIN = {
    'id': 'RP039',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Timezone',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Localisation',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change the system timezone?',
    'inputs': [
        {
            'name': 'timezone',
            'label': 'Timezone, e.g. Asia/Shanghai',
            'type': 'text',
            'pattern': '[A-Za-z0-9_+./-]{1,64}',
            'required': True,
        },
    ],
    'timeout_s': 10,
    'documentation': {
        'title': '时区',
        'criterion': '验证 zoneinfo 路径后设置。',
    },
}


def probe(timezone, root=Path('/usr/share/zoneinfo'), run=subprocess.run):
    if (not isinstance(timezone, str) or not re.fullmatch(r'[A-Za-z0-9_+./-]{1,64}', timezone)
            or '..' in timezone.split('/') or timezone.startswith('/')):
        return result('error', 'Invalid timezone')
    zone = root / timezone
    if not zone.is_file() or not zone.resolve().is_relative_to(root.resolve()):
        return result('fail', 'Timezone is not installed')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        completed = run(['timedatectl', 'set-timezone', timezone],
                        capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass' if completed.returncode == 0 else 'fail',
                  f'Timezone set to {timezone}' if completed.returncode == 0 else
                  'Timezone update failed',
                  details={'stderr': completed.stderr[-1000:]})


if __name__ == '__main__':
    print(json.dumps(probe(plugin_params()['timezone']), ensure_ascii=False))
