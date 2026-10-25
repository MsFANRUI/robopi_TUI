#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Configure X11 or Labwc screen blanking."""

import json
import os
from pathlib import Path
import pwd
import re

from loader.plugin_helpers import atomic_write, plugin_params, result

PLUGIN = {
    'id': 'RP046',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Screen blanking',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Display',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change screen blanking? Restart the desktop to apply.',
    'inputs': [
        {
            'name': 'backend',
            'label': 'Desktop backend',
            'type': 'choice',
            'choices': ['x11', 'labwc'],
            'required': True,
        },
        {
            'name': 'operation',
            'label': 'Blanking',
            'type': 'choice',
            'choices': ['enable', 'disable'],
            'required': True,
        },
        {
            'name': 'username',
            'label': 'Desktop user',
            'type': 'text',
            'pattern': '[a-z_][a-z0-9_-]{0,31}',
            'required': True,
            'when': {'backend': 'labwc'},
        },
    ],
    'timeout_s': 5,
    'documentation': {
        'title': 'X11/Labwc 熄屏',
        'criterion': 'X11 配置文本内嵌；Labwc 管理用户与 greeter 的 autostart。',
    },
}


IDLE_LINE = "swayidle -w timeout 600 'wlopm --off \\*' resume 'wlopm --on \\*' &"
X11_BLANKING_DISABLED = '''Section "Extensions"
    Option      "DPMS" "Disable"
EndSection

Section "ServerLayout"
    Identifier "ServerLayout0"
    Option "StandbyTime" "0"
    Option "SuspendTime" "0"
    Option "OffTime"     "0"
    Option "BlankTime"   "0"
EndSection
'''


def probe(backend, operation, username=None,
          setting=Path('/etc/X11/xorg.conf.d/10-blanking.conf'),
          greeter=Path('/etc/xdg/labwc-greeter/autostart')):
    if backend not in ('x11', 'labwc') or operation not in ('enable', 'disable'):
        return result('error', 'Invalid blanking operation')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        if backend == 'x11':
            if operation == 'enable':
                setting.unlink(missing_ok=True)
            else:
                atomic_write(setting, X11_BLANKING_DISABLED)
        else:
            if not username or not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username):
                return result('error', 'Select a local desktop user')
            account = pwd.getpwnam(username)
            autostart = Path(account.pw_dir) / '.config/labwc/autostart'
            for path in (autostart, greeter):
                if path == greeter and not path.parent.is_dir():
                    continue
                lines = path.read_text().splitlines() if path.exists() else []
                lines = [line for line in lines if line not in (IDLE_LINE,
                                                                '# robopi-tui screen blanking')]
                if operation == 'enable':
                    lines.extend(('# robopi-tui screen blanking', IDLE_LINE))
                atomic_write(path, '\n'.join(lines) + '\n')
                if path == autostart:
                    os.chown(path, account.pw_uid, account.pw_gid)
    except KeyError:
        return result('fail', 'Desktop user does not exist')
    except OSError as exc:
        return result('error', str(exc))
    return result('needs_review', f'{backend} screen blanking {operation}d; verify after restart')


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
