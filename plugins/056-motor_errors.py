#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 RoboParty

"""Read-only motor error/state snapshot (never enables or transmits)."""

import json

from loader import motor_status
from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP056',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'Motor error snapshot',
    'version': '1.0',
    'lifecycle': 'testing',
    'generic': False,
    'safety': 'query',
    'category': 'Motor',
    'batch': False,
    'requires': ['can'],
    'depends_on': ['RP007'],
    'timeout_s': 15,
    'documentation': {
        'title': '电机错误快照',
        'criterion': '逐台读取反馈错误码与状态；无反馈标记 needs_review；不使能、不发送 CAN 帧。',
    },
}


def probe(config=None, read=motor_status.read):
    try:
        data = read(config)
    except (OSError, ValueError, ImportError) as exc:
        return result('error', f'Could not read motor status: {exc}')
    motors = data.get('motors', [])
    errors = [motor for motor in motors if motor.get('feedback') and motor.get('error')]
    missing = [motor for motor in motors if not motor.get('feedback')]
    details = {
        'config': data.get('config'),
        'settle_seconds': data.get('settleSeconds'),
        'motors': motors,
        'warnings': data.get('warnings', []),
    }
    if errors:
        text = ', '.join(f"{m['id']}:{m['errorName']}" for m in errors)
        return result('fail', 'Motor errors: ' + text, value=len(errors), details=details)
    if missing:
        ids = ', '.join(str(motor['id']) for motor in missing)
        return result('needs_review', 'No feedback from motor(s): ' + ids, value=0,
                      details=details)
    return result('pass', f'{len(motors)} motor(s) report no errors', value=0,
                  details=details)


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
