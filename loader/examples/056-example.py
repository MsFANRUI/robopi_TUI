#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Copy this file to plugins/ and replace the placeholder with a real check."""

import json


PLUGIN = {
    'id': 'RP056',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'Example check (not implemented)',
    'documentation': {
        'title': '示例测试',
        'criterion': '示例只返回 skip；实现真实判据后才可返回 pass。',
    },
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'test',
    'category': 'System',
    'batch': False,
    'safety': 'passive',
    'requires': [],
    'depends_on': [],
    'timeout_s': 10,
}


def probe():
    return {'status': 'skip', 'message': 'Example only; implement a real check',
            'value': None, 'unit': None, 'details': {}}


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
