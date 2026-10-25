#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Change a local account password through chpasswd stdin."""

import json
import os
import pwd
import re
import subprocess

from loader.plugin_helpers import plugin_params, result

PLUGIN = {
    'id': 'RP043',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Local user password',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'System',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change this account password now?',
    'inputs': [
        {
            'name': 'username',
            'label': 'Local user (root for administrator password)',
            'type': 'text',
            'pattern': '[a-z_][a-z0-9_-]{0,31}',
            'required': True,
        },
        {
            'name': 'password',
            'label': 'New password',
            'type': 'secret',
            'pattern': '[^\r\n:]{8,128}',
            'required': True,
        },
    ],
    'timeout_s': 10,
    'documentation': {
        'title': '本地用户密码',
        'criterion': '密码经 stdin 传给 chpasswd，不写报告。',
    },
}


def probe(username, password, run=subprocess.run):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username):
        return result('error', 'Invalid username')
    if not re.fullmatch(r'[^\r\n:]{8,128}', password):
        return result('error', 'Password must have 8-128 characters without colon/newline')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        pwd.getpwnam(username)
        completed = run(['chpasswd'], input=f'{username}:{password}\n',
                        capture_output=True, text=True, timeout=5, check=False)
    except KeyError:
        return result('fail', 'Local account does not exist')
    except (OSError, subprocess.TimeoutExpired):
        return result('error', 'Password update could not complete')
    return result('pass' if completed.returncode == 0 else 'fail',
                  'Password updated' if completed.returncode == 0 else 'Password update failed',
                  details={'username': username})


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
