#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Fail when any readable board thermal zone reaches 90 C."""

import json
from pathlib import Path


PLUGIN = {
    'id': 'RP001',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'Board temperature',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'System',
    'requires': ['thermal'],
    'timeout_s': 5,
    'documentation': {
        'title': '板卡温度',
        'criterion': '最高可读温区低于 90°C；无可读温区则跳过。',
    },
}


THERMAL_ROOT = Path('/sys/class/thermal')
MAX_TEMP_C = 90.0


def measure(root=THERMAL_ROOT):
    zones = []
    for temp_file in sorted(root.glob('thermal_zone*/temp')):
        try:
            temperature = int(temp_file.read_text().strip()) / 1000
            sensor_type = (temp_file.parent / 'type').read_text().strip()
        except (OSError, ValueError):
            continue
        if -40 <= temperature <= 150:
            zones.append((sensor_type, temperature, temp_file.parent.name))
    if not zones:
        return {'status': 'skip', 'value': None, 'unit': None,
                'message': 'No readable thermal zone', 'details': {}}
    sensor_type, temperature, zone = max(zones, key=lambda item: item[1])
    status = 'pass' if temperature < MAX_TEMP_C else 'fail'
    return {'status': status, 'value': round(temperature, 2), 'unit': 'C',
            'message': f'Hottest zone is {temperature:.2f} C; limit is below {MAX_TEMP_C:.0f} C',
            'details': {'sensor': sensor_type, 'zone': zone, 'limit_c': MAX_TEMP_C,
                        'zones': [{'sensor': sensor, 'temperature_c': value, 'zone': name}
                                  for sensor, value, name in zones]}}


if __name__ == '__main__':
    print(json.dumps(measure(), ensure_ascii=False))
