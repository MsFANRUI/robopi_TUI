#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Check the configured BMS port without opening it or restarting the daemon."""

import json
from pathlib import Path
import shlex

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP020',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'BMS port readiness',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'BMS',
    'requires': [],
    'timeout_s': 5,
    'documentation': {
        'title': 'BMS 端口就绪',
        'criterion': 'BMS 类型与端口已配置，相应 CAN 接口或串口存在；不证明通信。',
    },
}


CONFIG = Path('/etc/default/bms_daemon')
NET_ROOT = Path('/sys/class/net')


def configuration(path):
    values = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        key, separator, raw = line.partition('=')
        key = key.strip()
        if separator and key in ('BMS_TYPE', 'BMS_PORT'):
            parsed = shlex.split(raw, comments=True)
            if len(parsed) == 1:
                values[key] = parsed[0]
    return values


def probe(config=CONFIG, net_root=NET_ROOT):
    try:
        values = configuration(config)
    except FileNotFoundError:
        return result('skip', 'BMS configuration is not installed')
    except (OSError, ValueError) as exc:
        return result('error', f'Could not read BMS configuration: {exc}')
    kind, port = values.get('BMS_TYPE'), values.get('BMS_PORT')
    if not kind or not port:
        return result('fail', 'BMS_TYPE or BMS_PORT is not configured')
    if kind == 'GFCAN':
        present = '/' not in port and (net_root / port).is_dir()
        port_type = 'can'
    else:
        present = Path(port).is_char_device() if port.startswith('/dev/') else False
        port_type = 'serial'
    status = 'pass' if present else 'fail'
    message = ('BMS port exists; communication was not tested' if present
               else 'Configured BMS port is missing')
    return result(status, message,
                  details={'type': kind, 'port': port, 'port_type': port_type})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
