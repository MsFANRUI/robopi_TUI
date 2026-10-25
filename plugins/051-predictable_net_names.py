#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Control systemd predictable network interface naming on next boot."""

import json
import os
from pathlib import Path

from loader.plugin_helpers import plugin_params, result

PLUGIN = {
    'id': 'RP051',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Predictable network names',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Network',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change network interface naming? Names may change after reboot.',
    'inputs': [
        {
            'name': 'operation',
            'label': 'Predictable names',
            'type': 'choice',
            'choices': ['enable', 'disable'],
            'required': True,
        },
    ],
    'timeout_s': 5,
    'documentation': {
        'title': '可预测网卡名',
        'criterion': '设置 systemd link 掩码，重启后生效。',
    },
}


LINKS = (Path('/etc/systemd/network/99-default.link'),
         Path('/etc/systemd/network/73-usb-net-by-mac.link'))


def probe(operation, links=LINKS, cmdline=Path('/proc/cmdline')):
    if operation not in ('enable', 'disable'):
        return result('error', 'Invalid naming operation')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    if operation == 'enable' and 'net.ifnames=0' in cmdline.read_text().split():
        return result('fail', 'Kernel command line forces legacy interface names')
    try:
        if operation == 'disable':
            if any(path.exists() and not path.is_symlink() for path in links):
                return result('fail', 'A network link policy is an existing regular file')
            for path in links:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.unlink(missing_ok=True)
                path.symlink_to('/dev/null')
        else:
            for path in links:
                if path.is_symlink() and path.resolve() == Path('/dev/null'):
                    path.unlink()
    except OSError as exc:
        return result('error', str(exc))
    return result('pass', f'Predictable network names {operation}d; reboot required')


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
