#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Observe an addon SIG edge and hold both outputs high until the test ends."""

import json
import os
from pathlib import Path
import signal
import time

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP019',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Addon SIG dual-output test',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'active',
    'category': 'Addon',
    'confirm': 'Confirm SIG is GPIO voltage, not 5 V, before testing both outputs.',
    'requires': ['gpio'],
    'timeout_s': 25,
    'documentation': {
        'title': 'Addon SIG 双输出测试',
        'criterion': '15 秒内检测到 SIG 上升沿后仍需确认物理输出。',
    },
}


GPIO_ROOT = Path('/sys/class/gpio')
SIG = 61  # GPIO1_D5 / CN5-5
OUTPUTS = (40, 18)  # GPIO1_B0 / CN5-2; GPIO0_C2 / CN5-4


class TestInterrupted(Exception):
    pass


def stop_on_signal(signum, frame):
    raise TestInterrupted(f'Signal {signum} interrupted the SIG test')


def gpio(root, number, wait=time.sleep):
    path = root / f'gpio{number}'
    if path.is_dir():
        return path
    (root / 'export').write_text(str(number), encoding='ascii')
    for _ in range(100):
        if path.is_dir():
            return path
        wait(0.01)
    raise OSError(f'GPIO{number} sysfs node was not created')


def probe(root=GPIO_ROOT, is_root=None, clock=time.monotonic, pause=time.sleep,
          window_s=15):
    if not (os.geteuid() == 0 if is_root is None else is_root()):
        return result('fail', 'SIG test requires root')
    paths = {}
    edge_seen = False
    failure = None
    restore_errors = []
    old_handlers = {number: signal.getsignal(number) for number in
                    (signal.SIGINT, signal.SIGTERM)}
    try:
        for number in old_handlers:
            signal.signal(number, stop_on_signal)
        for number in (SIG, *OUTPUTS):
            paths[number] = gpio(root, number, pause)
        (paths[SIG] / 'direction').write_text('in', encoding='ascii')
        for number in OUTPUTS:
            (paths[number] / 'direction').write_text('low', encoding='ascii')
        previous = (paths[SIG] / 'value').read_text(encoding='ascii').strip()
        if previous not in ('0', '1'):
            raise ValueError(f'Invalid SIG level: {previous!r}')
        deadline = clock() + window_s
        while clock() < deadline:
            current = (paths[SIG] / 'value').read_text(encoding='ascii').strip()
            if current not in ('0', '1'):
                raise ValueError(f'Invalid SIG level: {current!r}')
            if not edge_seen and previous == '0' and current == '1':
                for number in OUTPUTS:
                    (paths[number] / 'direction').write_text('high', encoding='ascii')
                edge_seen = True
            previous = current
            pause(0.01 if not edge_seen else min(0.1, max(0, deadline - clock())))
    except (OSError, ValueError, TestInterrupted) as exc:
        failure = str(exc)
    finally:
        for number in OUTPUTS:
            if number in paths:
                try:
                    (paths[number] / 'direction').write_text('low', encoding='ascii')
                except OSError as exc:
                    restore_errors.append(f'GPIO{number}: {exc}')
        for number, handler in old_handlers.items():
            signal.signal(number, handler)
    if restore_errors:
        return result('error', 'Could not restore SIG outputs LOW: '
                      + '; '.join(restore_errors), details={'edge_seen': edge_seen})
    if failure:
        return result('error', f'SIG test stopped: {failure}',
                      details={'edge_seen': edge_seen, 'outputs_restored_low': True})
    if edge_seen:
        return result('needs_review', 'SIG edge observed; verify both physical outputs',
                      details={'edge_seen': True, 'outputs_restored_low': True})
    return result('fail', 'No SIG rising edge was observed within 15 seconds',
                  details={'edge_seen': False, 'outputs_restored_low': True})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
