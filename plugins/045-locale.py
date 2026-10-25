#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Set a supported system locale."""

import json
import os
from pathlib import Path
import re
import subprocess

from loader.plugin_helpers import atomic_write, plugin_params, result

PLUGIN = {
    'id': 'RP045',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'System locale',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Localisation',
    'batch': False,
    'safety': 'active',
    'confirm': 'Generate and select this system locale?',
    'inputs': [
        {
            'name': 'locale',
            'label': 'Locale, e.g. zh_CN.UTF-8',
            'type': 'text',
            'pattern': '[A-Za-z_]+(?:\\.[A-Za-z0-9-]+)?',
            'required': True,
        },
    ],
    'timeout_s': 90,
    'documentation': {
        'title': '区域设置',
        'criterion': '仅接受 SUPPORTED 中的 locale。',
    },
}


def probe(locale, supported=Path('/usr/share/i18n/SUPPORTED'),
          generated=Path('/etc/locale.gen'), run=subprocess.run):
    if not re.fullmatch(r'[A-Za-z_]+(?:\.[A-Za-z0-9-]+)?', locale):
        return result('error', 'Invalid locale')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    try:
        matches = [line for line in supported.read_text().splitlines()
                   if line.split(' ', 1)[0] == locale]
        if len(matches) != 1:
            return result('fail', 'Locale is not in the installed SUPPORTED list')
        if generated.is_symlink():
            return result('fail', 'Refusing to replace symlinked locale.gen')
        original = generated.read_text() if generated.exists() else ''
        lines = [line for line in original.splitlines()
                 if line.strip().lstrip('#').strip().split(' ', 1)[0] != locale]
        lines.append(matches[0])
        atomic_write(generated, '\n'.join(lines) + '\n')
        built = run(['locale-gen'], capture_output=True, text=True, timeout=70, check=False)
        if built.returncode:
            return result('fail', 'locale-gen failed', details={'stderr': built.stderr[-1000:]})
        updated = run(['update-locale', f'LANG={locale}'], capture_output=True,
                      text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass' if updated.returncode == 0 else 'fail',
                  f'Locale set to {locale}' if updated.returncode == 0 else 'update-locale failed',
                  details={'stderr': updated.stderr[-1000:]})


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
