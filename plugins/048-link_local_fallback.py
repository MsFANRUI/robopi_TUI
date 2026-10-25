#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Persist NetworkManager IPv4 link-local fallback policy."""

import json
import os
from pathlib import Path
import subprocess

from loader.plugin_helpers import atomic_write, plugin_params, result

PLUGIN = {
    'id': 'RP048',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'IPv4 link-local fallback',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Network',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change IPv4 link-local fallback? Network configuration may change.',
    'inputs': [
        {
            'name': 'operation',
            'label': 'Link-local fallback',
            'type': 'choice',
            'choices': ['enable', 'disable'],
            'required': True,
        },
    ],
    'timeout_s': 10,
    'documentation': {
        'title': '链路本地回退',
        'criterion': '修改 NetworkManager 配置并重新加载。',
    },
}


def probe(operation, path=Path('/etc/NetworkManager/conf.d/link-local.conf'),
          run=subprocess.run):
    if operation not in ('enable', 'disable'):
        return result('error', 'Invalid link-local operation')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        if operation == 'enable':
            atomic_write(path, '[connection]\nipv4.link-local=4\n')
        else:
            path.unlink(missing_ok=True)
        reloaded = run(['systemctl', 'reload', 'NetworkManager'], capture_output=True,
                       text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass' if reloaded.returncode == 0 else 'needs_review',
                  f'Link-local fallback {operation}d; NetworkManager reload '
                  f'exit {reloaded.returncode}')


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
