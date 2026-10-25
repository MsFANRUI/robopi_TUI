#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Read enumerated USB descriptors from sysfs."""

import json
from pathlib import Path

from loader.plugin_helpers import read_text, result


PLUGIN = {
    'id': 'RP011',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'USB device inventory',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'USB',
    'requires': ['usb'],
    'timeout_s': 5,
    'documentation': {
        'title': 'USB 设备清单',
        'criterion': '记录 USB 设备和枚举速率，结果待人工复核。',
    },
}


USB_ROOT = Path('/sys/bus/usb/devices')


def usb_devices(root=USB_ROOT):
    found = []
    for vendor_file in sorted(root.glob('*/idVendor')):
        directory = vendor_file.parent
        found.append({'device': directory.name, 'vendor_id': read_text(vendor_file),
                      'product_id': read_text(directory / 'idProduct'),
                      'name': read_text(directory / 'product'),
                      'speed_mbps': read_text(directory / 'speed'),
                      'usb_version': read_text(directory / 'version'),
                      'device_version': read_text(directory / 'bcdDevice')})
    return found


def probe(root=USB_ROOT):
    found = usb_devices(root)
    if not found:
        return result('skip', 'No USB devices found')
    return result('needs_review', f'{len(found)} USB device(s) enumerated',
                  value=len(found), unit='devices', details={'devices': found})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
