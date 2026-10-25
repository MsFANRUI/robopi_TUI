#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Enable or disable one serial-getty service."""

import json
import os
import re
import subprocess

from loader.plugin_helpers import plugin_params, result


PLUGIN = {
    'id': 'RP030',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Serial getty control',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Serial',
    'batch': False,
    'safety': 'active',
    'confirm': 'Changing serial getty may disconnect a console session. Continue?',
    'inputs': [
        {
            'name': 'port',
            'label': 'Serial port',
            'type': 'text',
            'pattern': 'tty(?:S|AMA|USB|ACM)[0-9]+',
            'required': True,
        },
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
        'title': '串口 getty',
        'criterion': '明确选择端口和启停。',
    },
}


def probe(port, operation, run=subprocess.run):
    if not re.fullmatch(r'tty(?:S|AMA|USB|ACM)[0-9]+', port):
        return result('error', 'Invalid serial port')
    if operation not in ('enable', 'disable'):
        return result('error', 'Invalid getty operation')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        service = f'serial-getty@{port}.service'
        completed = run(['systemctl', operation, '--now', service],
                        capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass' if completed.returncode == 0 else 'fail',
                  f'{service}: {operation} exit {completed.returncode}',
                  details={'stderr': completed.stderr[-1000:]})


if __name__ == '__main__':
    params = plugin_params()
    print(json.dumps(probe(params['port'], params['operation']), ensure_ascii=False))
