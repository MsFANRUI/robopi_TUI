#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Read GPIO line information without requesting or driving lines."""

import json
from pathlib import Path
import shutil
import subprocess

from loader.plugin_helpers import read_text, result


PLUGIN = {
    'id': 'RP015',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'GPIO line snapshot',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'Interfaces',
    'requires': ['gpio'],
    'timeout_s': 5,
    'documentation': {
        'title': 'GPIO 引脚快照',
        'criterion': '记录 GPIO 状态，结果待人工复核。',
    },
}


DEBUG_GPIO = Path('/sys/kernel/debug/gpio')


def probe(debug_path=DEBUG_GPIO, gpioinfo=shutil.which('gpioinfo')):
    snapshot = read_text(debug_path)
    source = str(debug_path)
    if not snapshot and gpioinfo:
        try:
            completed = subprocess.run([gpioinfo], capture_output=True, text=True,
                                       timeout=2, check=False)
            snapshot = completed.stdout.strip() if completed.returncode == 0 else ''
            source = 'gpioinfo'
        except (OSError, subprocess.TimeoutExpired):
            pass
    if not snapshot:
        return result('skip', 'GPIO information is unavailable')
    return result('needs_review', 'GPIO line information captured',
                  details={'source': source, 'snapshot': snapshot[:16384],
                           'truncated': len(snapshot) > 16384})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
