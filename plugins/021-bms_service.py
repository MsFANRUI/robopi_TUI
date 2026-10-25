#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Check the running BMS daemon and recent live data from its current invocation."""

import json
import re
import subprocess

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP021',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'BMS service and live data',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'BMS',
    'requires': [],
    'depends_on': ['RP020'],
    'timeout_s': 12,
    'documentation': {
        'title': 'BMS 服务与实时数据',
        'criterion': '服务 active/running，最近 30 秒有本次启动的 BMS 数据日志。',
    },
}


DATA_LINE = re.compile(r'\[BMS Data\]|\[CAN BMS Data\]|\[NRF PMIC\]')
INVOCATION = re.compile(r'[0-9a-fA-F]{32}\Z')


def service_state():
    completed = subprocess.run(
        ['systemctl', 'show', 'bms.service', '--property=ActiveState,SubState,Result,'
         'ExecMainStatus,InvocationID'], capture_output=True, text=True, timeout=3,
        check=True)
    return dict(line.split('=', 1) for line in completed.stdout.splitlines() if '=' in line)


def recent_logs(invocation):
    return subprocess.run(
        ['journalctl', f'_SYSTEMD_INVOCATION_ID={invocation}', '--since=-30s',
         '--no-pager', '-o', 'short-iso-precise'], capture_output=True, text=True, timeout=5,
        check=True).stdout


def probe(state=service_state, logs=recent_logs):
    try:
        fields = state()
        details = {key: fields.get(key, '') for key in
                   ('ActiveState', 'SubState', 'Result', 'ExecMainStatus', 'InvocationID')}
        if (details['ActiveState'] != 'active' or details['SubState'] != 'running'
                or details['Result'] != 'success' or details['ExecMainStatus'] != '0'):
            return result('fail', 'bms.service is not running cleanly', details=details)
        invocation = details['InvocationID']
        if not INVOCATION.fullmatch(invocation):
            return result('fail', 'bms.service has no current invocation ID', details=details)
        output = logs(invocation)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return result('error', f'Could not inspect bms.service: {exc}')
    matches = [line[:300] for line in output.splitlines() if DATA_LINE.search(line)]
    details['recent_data_lines'] = matches[-5:]
    if not matches:
        return result('fail', 'bms.service is active but has no live data in the last 30 seconds',
                      details=details)
    return result('pass', 'bms.service is running and reporting live data', details=details)


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
