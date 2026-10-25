#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Run apt-get update followed by apt-get upgrade."""

import json
import os
import signal
import subprocess

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP006',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'APT update and upgrade',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'active',
    'category': 'System',
    'confirm': 'Run apt-get update and upgrade on this board?',
    'requires': ['apt'],
    'timeout_s': 3100,
    'documentation': {
        'title': 'APT 更新与升级',
        'criterion': '`apt-get update` 和 `apt-get -y upgrade` 均成功。',
    },
}


COMMANDS = (
    ('update', ['apt-get', 'update'], 900),
    ('upgrade', ['apt-get', '-y', '-o', 'Dpkg::Options::=--force-confdef',
                 '-o', 'Dpkg::Options::=--force-confold', 'upgrade'], 2100),
)


def run_command(command, timeout):
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, start_new_session=True,
                               env={**os.environ, 'DEBIAN_FRONTEND': 'noninteractive'})
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)


def probe(run=None, is_root=None):
    if not (os.geteuid() == 0 if is_root is None else is_root()):
        return result('fail', 'APT upgrade requires root')
    if run is None:
        run = run_command
    logs = {}
    for stage, command, timeout in COMMANDS:
        try:
            completed = run(command, timeout)
        except (OSError, subprocess.TimeoutExpired) as exc:
            return result('error', f'APT {stage} could not complete: {exc}',
                          details={'stage': stage, 'logs': logs})
        logs[stage] = {'exit_code': completed.returncode,
                       'stdout': completed.stdout[-12000:],
                       'stderr': completed.stderr[-12000:]}
        if completed.returncode:
            return result('fail', f'APT {stage} failed',
                          details={'stage': stage, 'logs': logs})
    return result('pass', 'APT update and upgrade completed', details={'logs': logs})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
