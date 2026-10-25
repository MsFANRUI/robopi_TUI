#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Require an external SuperSpeed USB hub to be enumerated."""

import json
from pathlib import Path

from loader.plugin_helpers import read_text, result


PLUGIN = {
    'id': 'RP012',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'USB 3.0 expansion hub',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'USB',
    'requires': ['usb'],
    'timeout_s': 5,
    'documentation': {
        'title': 'USB 3.0 扩展坞',
        'criterion': '外部 Hub 的设备类或接口类为 `09`，速率至少 5000 Mb/s。',
    },
}


USB_ROOT = Path('/sys/bus/usb/devices')


def probe(root=USB_ROOT):
    hubs = []
    for vendor_file in sorted(root.glob('*/idVendor')):
        directory = vendor_file.parent
        if '-' not in directory.name:
            continue
        try:
            speed = float(read_text(directory / 'speed'))
        except ValueError:
            continue
        try:
            device_class = int(read_text(directory / 'bDeviceClass'), 16)
        except ValueError:
            device_class = -1
        interface_classes = [read_text(path) for path in
                             root.glob(directory.name + ':*/bInterfaceClass')]
        is_hub = device_class == 9 or '09' in interface_classes
        if is_hub and speed >= 5000:
            hubs.append({'device': directory.name, 'vendor_id': read_text(vendor_file),
                         'product_id': read_text(directory / 'idProduct'),
                         'name': read_text(directory / 'product'),
                         'speed_mbps': read_text(directory / 'speed'),
                         'usb_version': read_text(directory / 'version'),
                         'device_version': read_text(directory / 'bcdDevice')})
    return result('pass' if hubs else 'fail',
                  f'{len(hubs)} external SuperSpeed USB hub(s) enumerated',
                  value=len(hubs), unit='hubs', details={'hubs': hubs})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
