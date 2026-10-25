#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Drive one selected LED pattern for visual inspection."""

import argparse
import json
import os
import subprocess
import sys

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP018',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Addon LED visual test',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'active',
    'category': 'Addon',
    'batch': False,
    'confirm': 'Set the selected LED pattern? Verify the output visually.',
    'inputs': [
        {
            'name': 'mode',
            'label': 'LED pattern',
            'type': 'choice',
            'choices': ['demo', 'red', 'green', 'blue', 'off'],
            'required': True,
        },
    ],
    'requires': [],
    'depends_on': ['RP017'],
    'timeout_s': 20,
    'documentation': {
        'title': 'Addon LED 目视测试',
        'criterion': '点灯工具成功后仍需目视确认。',
    },
}


MODES = {'demo': ['demo'], 'red': ['solid', '32', '0', '0'],
         'green': ['solid', '0', '32', '0'], 'blue': ['solid', '0', '0', '32'],
         'off': ['off']}


def probe(mode, run=subprocess.run, is_root=None):
    if mode not in MODES:
        return result('fail', 'Select demo, red, green, blue or off')
    if not (os.geteuid() == 0 if is_root is None else is_root()):
        return result('fail', 'Addon LED test requires root')
    try:
        completed = run(['robopi-ws2812', *MODES[mode]], capture_output=True,
                        text=True, timeout=12, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        return result('error', f'LED command could not complete: {exc}')
    details = {'mode': mode, 'exit_code': completed.returncode,
               'stdout': completed.stdout[-1000:], 'stderr': completed.stderr[-1000:]}
    if completed.returncode:
        return result('fail', 'LED command failed', details=details)
    return result('needs_review', 'LED command completed; verify the visible output',
                  details=details)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=tuple(MODES))
    parser.add_argument('--params')
    parser.add_argument('--params-stdin', action='store_true')
    args = parser.parse_args()
    params = (json.loads(sys.stdin.read() if args.params_stdin else args.params)
              if args.params is not None or args.params_stdin else {})
    print(json.dumps(probe(params.get('mode', args.mode)), ensure_ascii=False))
