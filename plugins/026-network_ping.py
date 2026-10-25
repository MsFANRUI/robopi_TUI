#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Check network reachability through a selected board interface."""

import json
from pathlib import Path
import re
import subprocess

from loader.plugin_helpers import plugin_params, result


PLUGIN = {
    'id': 'RP026',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'Network reachability',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'test',
    'category': 'Network',
    'batch': False,
    'safety': 'query',
    'requires': ['network'],
    'inputs': [
        {
            'name': 'interface',
            'label': 'Network interface',
            'type': 'text',
            'pattern': '[A-Za-z0-9_.-]{1,32}',
            'required': True,
        },
        {
            'name': 'target',
            'label': 'Ping target',
            'type': 'choice',
            'choices': ['www.roboparty.com', 'www.baidu.com', '8.8.8.8'],
            'required': True,
        },
    ],
    'timeout_s': 25,
    'documentation': {
        'title': '指定接口 Ping',
        'criterion': '选定接口和目标，5 次 Ping；不修改网络。',
    },
}


def probe(interface, target, root=Path('/sys/class/net'), run=subprocess.run):
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,32}', interface) or not (root / interface).exists():
        return result('fail', 'Network interface not found')
    if target not in PLUGIN['inputs'][1]['choices']:
        return result('error', 'Target is not allowed')
    try:
        completed = run(['ping', '-I', interface, '-c', '5', '-W', '2', target],
                        capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    return result('pass' if completed.returncode == 0 else 'fail',
                  f'Ping {target} via {interface}: exit {completed.returncode}',
                  details={'interface': interface, 'target': target,
                           'stdout': completed.stdout[-4000:],
                           'stderr': completed.stderr[-1000:]})


if __name__ == '__main__':
    params = plugin_params()
    print(json.dumps(probe(params['interface'], params['target']), ensure_ascii=False))
