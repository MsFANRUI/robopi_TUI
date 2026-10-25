#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Refresh APT and install the current robopi-tui package."""

import json
import os
import subprocess

from loader.plugin_helpers import result

PLUGIN = {
    'id': 'RP053',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Update RoboPi TUI',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'System',
    'batch': False,
    'safety': 'active',
    'confirm': 'Refresh APT and install the latest robopi-tui package?',
    'requires': ['apt'],
    'timeout_s': 1200,
    'documentation': {
        'title': '更新 RoboPi TUI',
        'criterion': 'APT 刷新并安装 robopi-tui。',
    },
}


def probe(run=subprocess.run):
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    for command in (['apt-get', 'update'], ['apt-get', '-y', 'install', 'robopi-tui']):
        try:
            completed = run(command, capture_output=True, text=True,
                            timeout=600, check=False,
                            env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})
        except (OSError, subprocess.TimeoutExpired) as exc:
            return result('error', f'APT operation stopped: {exc}')
        if completed.returncode:
            return result('fail', f'{command[1]} failed',
                          details={'stderr': completed.stderr[-2000:]})
    return result('pass', 'RoboPi TUI package updated; reopen the TUI')


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
