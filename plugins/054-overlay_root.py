#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Configure installed overlayroot through its local override file."""

import json
import os
from pathlib import Path
import subprocess

from loader.plugin_helpers import atomic_write, plugin_params, read_text, result

PLUGIN = {
    'id': 'RP054',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Read-only root overlay',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'System',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change overlayroot and regenerate initramfs? Reboot required; changes made under a running overlay would be lost.',
    'inputs': [
        {
            'name': 'operation',
            'label': 'Root overlay',
            'type': 'choice',
            'choices': ['enable', 'disable'],
            'required': True,
        },
    ],
    'timeout_s': 360,
    'documentation': {
        'title': '根目录 Overlay',
        'criterion': '使用 overlayroot.local.conf，重建 initramfs 后需重启。',
    },
}


def probe(operation, base=Path('/etc/overlayroot.conf'),
          local=Path('/etc/overlayroot.local.conf'),
          mounts=Path('/proc/mounts'), cmdline=Path('/proc/cmdline'),
          run=subprocess.run):
    if operation not in ('enable', 'disable'):
        return result('error', 'Invalid overlayroot operation')
    if not base.is_file():
        return result('skip', 'overlayroot is not installed')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    if any(line.split()[1:3] == ['/', 'overlay'] for line in read_text(mounts).splitlines()):
        return result('fail', 'Root is already an overlay; configuration would not persist')
    if any(word.startswith('overlayroot=') for word in read_text(cmdline).split()):
        return result('fail', 'Kernel command line overrides overlayroot configuration')
    try:
        if local.exists() and any(line.strip() and not line.lstrip().startswith('#')
                                  and not line.lstrip().startswith('overlayroot=')
                                  for line in local.read_text().splitlines()):
            return result('fail', 'Existing local overlayroot configuration has other settings')
        original = local.read_text() if local.exists() else None
        atomic_write(local, f'overlayroot="{"tmpfs" if operation == "enable" else ""}"\n')
        updated = run(['update-initramfs', '-u'], capture_output=True, text=True,
                      timeout=300, check=False)
        if updated.returncode:
            if original is None:
                local.unlink(missing_ok=True)
            else:
                atomic_write(local, original)
            return result('fail', 'initramfs update failed; configuration restored',
                          details={'stderr': updated.stderr[-2000:]})
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', f'Overlayroot update stopped: {exc}')
    return result('pass', f'Overlayroot {operation}d; reboot required')


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
