#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Explicitly configure/start or stop the ADB gadget daemon."""

import json
import os
import shutil
import subprocess

from loader.plugin_helpers import plugin_params, result


PLUGIN = {
    'id': 'RP028',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'ADB gadget control',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Interfaces',
    'batch': False,
    'safety': 'active',
    'confirm': 'This may disconnect the current ADB connection. Continue?',
    'inputs': [
        {
            'name': 'operation',
            'label': 'Operation',
            'type': 'choice',
            'choices': ['enable', 'disable'],
            'required': True,
        },
    ],
    'timeout_s': 35,
    'documentation': {
        'title': 'ADB gadget 控制',
        'criterion': '明确选择启停；可能断开 ADB。',
    },
}


def probe(operation, run=subprocess.run, spawn=subprocess.Popen):
    if operation not in ('enable', 'disable'):
        return result('error', 'Invalid ADB operation')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        if operation == 'enable':
            setup = shutil.which('set_device.sh')
            if setup:
                completed = run([setup], capture_output=True, text=True,
                                timeout=25, check=False)
                if completed.returncode:
                    return result('fail', 'Gadget setup failed',
                                  details={'stderr': completed.stderr[-1000:]})
            spawn(['adbd'], start_new_session=True, stdout=subprocess.DEVNULL,
                  stderr=subprocess.DEVNULL)
            return result('pass', 'Gadget configured and adbd launch requested')
        completed = run(['pkill', '-x', 'adbd'], capture_output=True, text=True,
                        timeout=5, check=False)
        return result('pass' if completed.returncode in (0, 1) else 'fail',
                      'adbd stopped' if completed.returncode in (0, 1) else 'Could not stop adbd')
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))


if __name__ == '__main__':
    params = plugin_params()
    print(json.dumps(probe(params['operation']), ensure_ascii=False))
