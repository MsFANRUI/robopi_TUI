#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Set an existing boot partition's mount policy in fstab."""

import json
import os
from pathlib import Path
import re

from loader.plugin_helpers import atomic_write, plugin_params, read_text, result

PLUGIN = {
    'id': 'RP055',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Boot partition write protection',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'System',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change boot partition mount policy in fstab? Reboot required.',
    'inputs': [
        {
            'name': 'operation',
            'label': 'Boot partition',
            'type': 'choice',
            'choices': ['read_only', 'writable'],
            'required': True,
        },
    ],
    'timeout_s': 5,
    'documentation': {
        'title': '启动分区写保护',
        'criterion': '修改现有 fstab 挂载选项，重启后生效。',
    },
}


def probe(operation, fstab=Path('/etc/fstab'), mounts=Path('/proc/mounts')):
    if operation not in ('read_only', 'writable'):
        return result('error', 'Invalid boot partition operation')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    if any(line.split()[1:3] == ['/', 'overlay'] for line in read_text(mounts).splitlines()):
        return result('fail', 'Root is currently overlaid; fstab change would not persist')
    try:
        original = fstab.read_text()
        lines = original.splitlines(keepends=True)
        found = []
        for index, line in enumerate(lines):
            fields = line.split()
            if not fields or fields[0].startswith('#') or len(fields) < 4:
                continue
            if fields[1] not in ('/boot', '/boot/firmware'):
                continue
            options = [option for option in fields[3].split(',') if option not in ('ro', 'rw')]
            options.append('ro' if operation == 'read_only' else 'rw')
            match = re.match(r'^(\s*\S+\s+\S+\s+\S+\s+)(\S+)(.*)$', line)
            if not match:
                return result('fail', 'Invalid boot partition fstab entry')
            lines[index] = match[1] + ','.join(options) + match[3]
            found.append(fields[1])
        if len(found) != 1:
            return result('fail', 'Expected exactly one boot partition fstab entry')
        atomic_write(fstab, ''.join(lines))
    except OSError as exc:
        return result('error', str(exc))
    return result('pass', f'Boot partition set {operation}; reboot required',
                  details={'mountpoint': found[0]})


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
