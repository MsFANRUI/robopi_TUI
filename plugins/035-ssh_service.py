#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Explicitly enable or disable the SSH service."""

import json
import os
import subprocess

from loader.plugin_helpers import plugin_params, result


PLUGIN = {
    'id': 'RP035',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'SSH service control',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'System',
    'batch': False,
    'safety': 'active',
    'confirm': 'Changing SSH may disconnect the current session. Continue?',
    'inputs': [
        {
            'name': 'operation',
            'label': 'Operation',
            'type': 'choice',
            'choices': ['enable', 'disable'],
            'required': True,
        },
    ],
    'timeout_s': 20,
    'documentation': {
        'title': 'SSH 服务',
        'criterion': '启停服务。',
    },
}


def probe(operation, run=subprocess.run):
    if operation not in ('enable', 'disable'):
        return result('error', 'Invalid SSH operation')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        completed = run(['systemctl', operation, '--now', 'ssh.service'],
                        capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass' if completed.returncode == 0 else 'fail',
                  f'SSH {operation}: exit {completed.returncode}',
                  details={'stderr': completed.stderr[-1000:]})


if __name__ == '__main__':
    print(json.dumps(probe(plugin_params()['operation']), ensure_ascii=False))
