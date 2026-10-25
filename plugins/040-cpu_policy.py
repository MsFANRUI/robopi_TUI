#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Inspect or configure CPU frequency policies."""

import json
import os
from pathlib import Path

from loader.plugin_helpers import plugin_params, read_text, result

PLUGIN = {
    'id': 'RP040',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'CPU frequency policy',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'action',
    'category': 'System',
    'batch': False,
    'safety': 'active',
    'confirm': 'Change CPU frequency policy on every available policy?',
    'inputs': [
        {
            'name': 'operation',
            'label': 'Operation',
            'type': 'choice',
            'choices': ['inspect', 'governor', 'limits'],
            'required': True,
        },
        {
            'name': 'governor',
            'label': 'Governor for governor operation',
            'type': 'text',
            'pattern': '[a-z0-9_-]{1,32}',
            'required': True,
            'when': {'operation': 'governor'},
        },
        {
            'name': 'minimum_mhz',
            'label': 'Minimum MHz for limits',
            'type': 'integer',
            'minimum': 1,
            'maximum': 10000,
            'required': True,
            'when': {'operation': 'limits'},
        },
        {
            'name': 'maximum_mhz',
            'label': 'Maximum MHz for limits',
            'type': 'integer',
            'minimum': 1,
            'maximum': 10000,
            'required': True,
            'when': {'operation': 'limits'},
        },
    ],
    'timeout_s': 10,
    'documentation': {
        'title': 'CPU 调频策略',
        'criterion': '查询或设置 governor/频率范围。',
    },
}


def probe(operation, governor=None, minimum_mhz=None, maximum_mhz=None,
          root=Path('/sys/devices/system/cpu/cpufreq')):
    policies = sorted(root.glob('policy*'))
    if not policies:
        return result('skip', 'No CPU frequency policies found')
    before = {p.name: {'governor': read_text(p / 'scaling_governor'),
                       'minimum_khz': read_text(p / 'scaling_min_freq'),
                       'maximum_khz': read_text(p / 'scaling_max_freq')}
              for p in policies}
    if operation == 'inspect':
        return result('pass', 'CPU policies captured', details={'policies': before})
    if os.geteuid() != 0:
        return result('fail', 'Root privileges required')
    if operation == 'governor':
        if not governor or any(governor not in read_text(p / 'scaling_available_governors').split()
                               for p in policies):
            return result('fail', 'Governor is not available on every CPU policy')
    elif operation == 'limits':
        if (type(minimum_mhz) is not int or type(maximum_mhz) is not int
                or minimum_mhz <= 0 or maximum_mhz < minimum_mhz):
            return result('error', 'Specify valid minimum and maximum MHz')
        low, high = minimum_mhz * 1000, maximum_mhz * 1000
        try:
            outside = any(low < int(read_text(p / 'cpuinfo_min_freq'))
                          or high > int(read_text(p / 'cpuinfo_max_freq'))
                          for p in policies)
        except ValueError:
            return result('error', 'CPU hardware limits are unreadable')
        if outside:
            return result('fail', 'Limits exceed a CPU policy hardware range')
    else:
        return result('error', 'Invalid CPU operation')
    try:
        for policy in policies:
            if operation == 'governor':
                (policy / 'scaling_governor').write_text(governor + '\n')
            else:
                current_max = int(read_text(policy / 'scaling_max_freq'))
                order = ('scaling_max_freq', 'scaling_min_freq') if low > current_max else (
                    'scaling_min_freq', 'scaling_max_freq')
                for key in order:
                    (policy / key).write_text(str(low if key == 'scaling_min_freq' else high) + '\n')
    except (OSError, ValueError) as exc:
        return result('error', f'CPU policy update stopped: {exc}', details={'before': before})
    return result('pass', 'CPU policy updated', details={'before': before})


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
