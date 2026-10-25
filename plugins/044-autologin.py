#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Configure console or LightDM autologin for a local user."""

import json
import os
from pathlib import Path
import pwd
import re
import subprocess

from loader.plugin_helpers import atomic_write, plugin_params, result

PLUGIN = {
    'id': 'RP044',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Automatic login',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'System',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change automatic login? Anyone with physical access may enter this account.',
    'inputs': [
        {
            'name': 'target',
            'label': 'Login target',
            'type': 'choice',
            'choices': ['console', 'desktop'],
            'required': True,
        },
        {
            'name': 'operation',
            'label': 'Operation',
            'type': 'choice',
            'choices': ['enable', 'disable'],
            'required': True,
        },
        {
            'name': 'username',
            'label': 'Local username',
            'type': 'text',
            'pattern': '[a-z_][a-z0-9_-]{0,31}',
            'required': True,
        },
    ],
    'timeout_s': 10,
    'documentation': {
        'title': '自动登录',
        'criterion': '控制终端或 LightDM 自动登录。',
    },
}


def probe(target, operation, username, console=Path('/etc/systemd/system/getty@tty1.service.d/autologin.conf'),
          lightdm=Path('/etc/lightdm/lightdm.conf'), run=subprocess.run):
    if (target not in ('console', 'desktop') or operation not in ('enable', 'disable')
            or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username)):
        return result('error', 'Invalid login setting')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        pwd.getpwnam(username)
        if target == 'console':
            if operation == 'enable':
                atomic_write(console, '[Service]\nExecStart=\n'
                             f'ExecStart=-/sbin/agetty --autologin {username} --noclear %I $TERM\n')
            else:
                console.unlink(missing_ok=True)
            changed = run(['systemctl', 'daemon-reload'], capture_output=True,
                          text=True, timeout=5, check=False)
            if changed.returncode:
                return result('fail', 'systemd daemon-reload failed')
        else:
            if not lightdm.parent.is_dir():
                return result('skip', 'LightDM is not installed')
            lines = lightdm.read_text().splitlines(keepends=True) if lightdm.exists() else []
            seat = next((index for index, line in enumerate(lines)
                         if line.strip() == '[Seat:*]'), None)
            if seat is None:
                lines.extend(['\n[Seat:*]\n', f'autologin-user={username if operation == "enable" else ""}\n'])
            else:
                end = next((index for index in range(seat + 1, len(lines))
                            if lines[index].lstrip().startswith('[')), len(lines))
                lines[seat + 1:end] = [line for line in lines[seat + 1:end]
                                       if not re.match(r'^\s*autologin-user\s*=', line)] + [
                                           f'autologin-user={username if operation == "enable" else ""}\n']
            atomic_write(lightdm, ''.join(lines))
    except KeyError:
        return result('fail', 'Local account does not exist')
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('needs_review', f'{target} autologin {operation}d; verify after restart',
                  details={'target': target, 'username': username})


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
