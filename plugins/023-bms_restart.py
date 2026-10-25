#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Restart the BMS daemon, then verify service state and fresh communication."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP023',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'BMS restart and communication',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'active',
    'category': 'BMS',
    'confirm': 'Restart bms.service and check recent live BMS data?',
    'requires': [],
    'depends_on': ['RP020'],
    'timeout_s': 60,
    'documentation': {
        'title': 'BMS 重启与通信',
        'criterion': '重启服务成功，10 秒后满足 RP021 的实时数据判据。',
    },
}


SERVICE_CHECK = Path(__file__).with_name('021-bms_service.py')


def probe(restart=subprocess.run, check=subprocess.run, pause=time.sleep, is_root=None):
    if not (os.geteuid() == 0 if is_root is None else is_root()):
        return result('fail', 'BMS restart test requires root')
    try:
        restarted = restart(['systemctl', 'restart', 'bms.service'],
                            capture_output=True, text=True, timeout=25, check=False)
        if restarted.returncode:
            return result('fail', 'bms.service restart failed',
                          details={'restart_exit_code': restarted.returncode,
                                   'stderr': restarted.stderr[-1000:]})
        pause(10)
        completed = check([sys.executable, str(SERVICE_CHECK)], capture_output=True,
                          text=True, timeout=12, check=False)
        if completed.returncode:
            return result('error', 'BMS health plugin could not run',
                          details={'stderr': completed.stderr[-1000:]})
        checked = json.loads(completed.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return result('error', f'BMS restart test could not complete: {exc}')
    return result(checked['status'], checked['message'],
                  details={'restart_exit_code': 0, 'health': checked.get('details', {})})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
