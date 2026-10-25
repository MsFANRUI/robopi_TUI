#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Control one local user's sudo password requirement."""

import json
import os
from pathlib import Path
import pwd
import re
import subprocess
import tempfile

from loader.plugin_helpers import atomic_write, plugin_params, result

PLUGIN = {
    'id': 'RP052',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Sudo password requirement',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'System',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change whether sudo requires a password for this user?',
    'inputs': [
        {
            'name': 'username',
            'label': 'Local user',
            'type': 'text',
            'pattern': '[a-z_][a-z0-9_-]{0,31}',
            'required': True,
        },
        {
            'name': 'operation',
            'label': 'Require password',
            'type': 'choice',
            'choices': ['enable', 'disable'],
            'required': True,
        },
    ],
    'timeout_s': 10,
    'documentation': {
        'title': 'sudo 密码策略',
        'criterion': '仅针对明确选择的本地用户，先经 visudo 校验。',
    },
}


def probe(username, operation, root=Path('/etc/sudoers.d'), run=subprocess.run):
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username) or operation not in ('enable', 'disable'):
        return result('error', 'Invalid sudo setting')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        pwd.getpwnam(username)
        path = root / f'010_{username}-nopasswd'
        if operation == 'disable':
            candidate = f'{username} ALL=(ALL) NOPASSWD: ALL\n'
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8') as tmp:
                tmp.write(candidate)
                tmp.flush()
                checked = run(['visudo', '-cf', tmp.name], capture_output=True,
                              text=True, timeout=3, check=False)
            if checked.returncode:
                return result('fail', 'visudo rejected the sudoers rule')
            atomic_write(path, candidate)
            os.chmod(path, 0o440)
        else:
            path.unlink(missing_ok=True)
            effective = run(['sudo', '-n', '-l', '-U', username], capture_output=True,
                            text=True, timeout=3, check=False)
            if effective.returncode:
                return result('needs_review', 'Could not verify the effective sudo rules',
                              details={'username': username})
            if 'NOPASSWD:' in effective.stdout:
                return result('needs_review', 'Another sudoers rule still grants NOPASSWD',
                              details={'username': username})
    except KeyError:
        return result('fail', 'Local account does not exist')
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass', f'Sudo password requirement {operation}d for {username}')


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
