#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Configure system shell and APT proxy settings."""

import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from loader.plugin_helpers import atomic_write, plugin_params, result

PLUGIN = {
    'id': 'RP050',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Network proxy',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Network',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change shell and APT proxy settings?',
    'inputs': [
        {
            'name': 'scheme',
            'label': 'Proxy target',
            'type': 'choice',
            'choices': ['all', 'http', 'https', 'ftp', 'rsync', 'no_proxy'],
            'required': True,
        },
        {
            'name': 'address',
            'label': 'Proxy URL or comma-separated exceptions; empty clears',
            'type': 'secret',
            'pattern': '[^\r\n]{1,512}',
        },
    ],
    'timeout_s': 5,
    'documentation': {
        'title': '代理',
        'criterion': '配置 shell 和 APT 代理；不记录地址值。',
    },
}


def probe(scheme, address='', shell=Path('/etc/profile.d/robopi-tui-proxy.sh'),
          apt=Path('/etc/apt/apt.conf.d/01robopi-tui-proxy'),
          legacy_shell=Path('/etc/profile.d/proxy.sh'),
          legacy_apt=Path('/etc/apt/apt.conf.d/01proxy')):
    if scheme not in ('all', 'http', 'https', 'ftp', 'rsync', 'no_proxy'):
        return result('error', 'Invalid proxy target')
    if (not isinstance(address, str) or '\n' in address or '\r' in address
            or '"' in address or '\\' in address or "'" in address):
        return result('error', 'Invalid proxy address')
    if address and scheme != 'no_proxy':
        try:
            parsed = urlsplit(address)
            valid = (parsed.scheme in ('http', 'https', 'socks5')
                     and parsed.hostname and not parsed.username and not parsed.password)
        except ValueError:
            valid = False
        if not valid:
            return result('fail', 'Proxy must be a URL without embedded credentials')
    if scheme == 'no_proxy' and address and not re.fullmatch(r'[A-Za-z0-9.,_*:-]{1,512}', address):
        return result('fail', 'Invalid proxy exception list')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    targets = ('http', 'https', 'ftp', 'rsync') if scheme == 'all' else (scheme,)
    try:
        shell_lines = shell.read_text().splitlines() if shell.exists() else []
        apt_lines = apt.read_text().splitlines() if apt.exists() else []
        old_shell = legacy_shell.read_text().splitlines() if legacy_shell.exists() else []
        old_apt = legacy_apt.read_text().splitlines() if legacy_apt.exists() else []
        for target in targets:
            key = target if target == 'no_proxy' else target + '_proxy'
            shell_lines = [line for line in shell_lines
                           if not line.startswith(f'export {key}=')
                           and not line.startswith(f'export {key.upper()}=')]
            if target in ('http', 'https', 'ftp'):
                apt_lines = [line for line in apt_lines
                             if not line.startswith(f'Acquire::{target}::Proxy ')]
                old_apt = [line for line in old_apt
                           if not line.startswith(f'Acquire::{target}::Proxy ')]
            old_shell = [line for line in old_shell
                         if not line.startswith(f'export {key}=')
                         and not line.startswith(f'export {key.upper()}=')]
            if address:
                shell_lines.append(f"export {key}='{address}'")
                shell_lines.append(f"export {key.upper()}='{address}'")
                if target in ('http', 'https', 'ftp'):
                    apt_lines.append(f'Acquire::{target}::Proxy "{address}";')
        atomic_write(shell, '\n'.join(shell_lines) + '\n')
        atomic_write(apt, '\n'.join(apt_lines) + '\n')
        if legacy_shell.exists():
            atomic_write(legacy_shell, '\n'.join(old_shell) + '\n')
        if legacy_apt.exists():
            atomic_write(legacy_apt, '\n'.join(old_apt) + '\n')
    except OSError as exc:
        return result('error', str(exc))
    return result('pass', 'Proxy setting updated for future sessions',
                  details={'scheme': scheme, 'configured': bool(address)})


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
