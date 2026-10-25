#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Select systemd-journald storage mode using a drop-in."""

import json
import os
from pathlib import Path
import subprocess

from loader.plugin_helpers import atomic_write, plugin_params, result

PLUGIN = {
    'id': 'RP049',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Journal storage',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'System',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change journal storage? Logging behavior changes immediately.',
    'inputs': [
        {
            'name': 'mode',
            'label': 'Storage mode',
            'type': 'choice',
            'choices': ['default', 'volatile', 'persistent', 'auto', 'none'],
            'required': True,
        },
    ],
    'timeout_s': 10,
    'documentation': {
        'title': 'journald 存储',
        'criterion': '写入独立 drop-in 并重启服务。',
    },
}


def probe(mode, path=Path('/etc/systemd/journald.conf.d/80-robopi-tui-storage.conf'),
          run=subprocess.run, legacy=Path('/etc/systemd/journald.conf.d/80-robopi-config-journal-storage.conf')):
    if mode not in ('default', 'volatile', 'persistent', 'auto', 'none'):
        return result('error', 'Invalid journal mode')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        if legacy.exists():
            old = legacy.read_text()
            if '# Created/managed by robopi-config' not in old:
                return result('fail', 'Existing legacy journal file is not managed by robopi-config')
        if mode == 'default':
            path.unlink(missing_ok=True)
        else:
            atomic_write(path, f'[Journal]\nStorage={mode}\n')
        legacy.unlink(missing_ok=True)
        restarted = run(['systemctl', 'restart', 'systemd-journald'],
                        capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass' if restarted.returncode == 0 else 'fail',
                  f'Journal storage {mode}; restart exit {restarted.returncode}')


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
