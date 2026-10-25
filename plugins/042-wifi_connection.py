#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Configure a NetworkManager Wi-Fi connection without exposing the PSK in argv."""

import json
import os
from pathlib import Path
import re
import subprocess
import uuid

from loader.plugin_helpers import plugin_params, result

PLUGIN = {
    'id': 'RP042',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Wi-Fi connection',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'Network',
    'batch': False,
    'safety': 'active',
    'confirm': 'Connect this board to the selected Wi-Fi network? The network may change.',
    'inputs': [
        {
            'name': 'interface',
            'label': 'Wireless interface',
            'type': 'text',
            'pattern': '[A-Za-z0-9_.-]{1,32}',
            'required': True,
        },
        {
            'name': 'ssid',
            'label': 'Wi-Fi SSID',
            'type': 'text',
            'pattern': '[A-Za-z0-9 _.-]{1,32}',
            'required': True,
        },
        {
            'name': 'password',
            'label': 'WPA password (8-63 characters)',
            'type': 'secret',
            'pattern': '[^\r\n]{8,63}',
            'required': True,
        },
    ],
    'timeout_s': 30,
    'documentation': {
        'title': 'Wi-Fi 连接',
        'criterion': 'NetworkManager 密钥文件以 0600 写入；连接可能中断。',
    },
}


def probe(interface, ssid, password, network=Path('/sys/class/net'),
          profiles=Path('/etc/NetworkManager/system-connections'), run=subprocess.run):
    if (not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', interface)
            or not (network / interface / 'wireless').is_dir()
            or not re.fullmatch(r'[A-Za-z0-9 _.-]{1,32}', ssid)
            or not re.fullmatch(r'[^\r\n]{8,63}', password)):
        return result('fail', 'Invalid Wi-Fi interface, SSID or WPA password')
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    identity = str(uuid.uuid4())
    path = profiles / f'robopi-tui-{identity}.nmconnection'
    # NetworkManager keyfile values cannot contain raw newlines or key separators.
    if any(char in password for char in ('\\', ';', '=')):
        return result('fail', 'Password contains characters unsupported by this keyfile writer')
    profile = (f'[connection]\nid=RoboPi {ssid}\nuuid={identity}\ntype=wifi\n'
               f'interface-name={interface}\n[wifi]\nmode=infrastructure\nssid={ssid}\n'
               f'[wifi-security]\nkey-mgmt=wpa-psk\npsk={password}\n'
               '[ipv4]\nmethod=auto\n[ipv6]\nmethod=auto\n')
    try:
        profiles.mkdir(parents=True, exist_ok=True)
        with path.open('x', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(profile)
            stream.flush()
            os.fsync(stream.fileno())
        loaded = run(['nmcli', 'connection', 'load', str(path)], capture_output=True,
                     text=True, timeout=10, check=False)
        if loaded.returncode:
            path.unlink(missing_ok=True)
            return result('fail', 'NetworkManager rejected the Wi-Fi profile')
        connected = run(['nmcli', 'connection', 'up', 'uuid', identity],
                        capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', f'Wi-Fi setup stopped: {exc}')
    return result('pass' if connected.returncode == 0 else 'fail',
                  'Wi-Fi connected' if connected.returncode == 0 else 'Wi-Fi connection failed',
                  details={'interface': interface, 'ssid': ssid, 'uuid': identity})


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
