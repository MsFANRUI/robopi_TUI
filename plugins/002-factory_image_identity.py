#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Compare the immutable image factory snapshot with the approved release."""

import json
from pathlib import Path
import shlex

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP002',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'Factory image identity',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'System',
    'requires': [],
    'timeout_s': 5,
    'documentation': {
        'title': '镜像出厂身份',
        'criterion': '`/etc/armbian-image-release` 的 8 个字段匹配出厂快照；不是 OTA 当前版本。',
    },
}


RELEASE = Path('/etc/armbian-image-release')
EXPECTED = {
    'BOARD': 'robopi2',
    'VENDOR': 'roboparty-os',
    'VERSION': '26.11.0-trunk-2.0.1',
    'REVISION': '26.11.0-trunk-2.0.1',
    'KERNEL_TARGET': 'current',
    'BUILD_REPOSITORY_COMMIT': 'da6b3f2ec-dirty',
    'IMAGE_UUID': '6e63c9b8-2fab-4387-8eab-51230e65b292',
    'EXTENSIONS': '',
}


def probe(path=RELEASE):
    try:
        lines = path.read_text(encoding='utf-8').splitlines()
    except OSError as exc:
        return result('fail', f'Cannot read factory image identity: {exc}')
    fields = {}
    for line in lines:
        key, separator, raw = line.partition('=')
        key = key.strip()
        if not separator or key not in EXPECTED:
            continue
        try:
            values = shlex.split(raw, comments=True)
        except ValueError as exc:
            return result('error', f'Invalid release field {key}: {exc}')
        if len(values) != 1 or key in fields:
            return result('error', f'Invalid or duplicate release field {key}')
        fields[key] = values[0]
    mismatches = {key: {'expected': expected, 'actual': fields.get(key)}
                  for key, expected in EXPECTED.items() if fields.get(key) != expected}
    return result('fail' if mismatches else 'pass',
                  'Factory image identity mismatch' if mismatches else 'Factory image identity matches',
                  details={'snapshot': fields, 'mismatches': mismatches})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
