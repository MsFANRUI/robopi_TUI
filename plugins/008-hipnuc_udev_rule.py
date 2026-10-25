#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Verify roboparty-base installs the HiPNUC CAN udev rule."""

import json
from pathlib import Path
import subprocess

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP008',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'HiPNUC udev rule',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'Interfaces',
    'requires': [],
    'timeout_s': 5,
    'documentation': {
        'title': 'HiPNUC udev 规则',
        'criterion': '`roboparty-base` 拥有已安装规则，且规则命名 `can_hipnuc`。',
    },
}


RULE = Path('/etc/udev/rules.d/99-can_hipnuc.rules')


def probe(query=None, rule=RULE):
    if query is None:
        query = lambda: subprocess.run(
            ['dpkg-query', '-L', 'roboparty-base'],
            capture_output=True, text=True, timeout=2, check=False)
    try:
        completed = query()
        if completed.returncode:
            return result('fail', 'roboparty-base is not installed',
                          details={'diagnostic': completed.stderr.strip()[:200]})
        if str(rule) not in completed.stdout.splitlines() or not rule.is_file():
            return result('fail', 'HiPNUC udev rule is missing from roboparty-base')
        content = rule.read_text(encoding='utf-8')
        if 'NAME="can_hipnuc"' not in content:
            return result('fail', 'HiPNUC udev rule does not name can_hipnuc')
        return result('pass', 'roboparty-base provides the can_hipnuc rule',
                      details={'package': 'roboparty-base', 'rule': str(rule)})
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return result('error', f'Could not inspect roboparty-base: {exc}')


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
