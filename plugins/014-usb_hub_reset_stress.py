#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Reset the USB hub for 100 cycles and archive each recovery check."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
import uuid

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP014',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'USB hub reset stress',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'active',
    'category': 'USB',
    'confirm': 'Reset the USB hub 100 times? Attached USB devices will disconnect.',
    'requires': ['usb'],
    'depends_on': ['RP012'],
    'timeout_s': 1200,
    'documentation': {
        'title': 'USB Hub 复位压力测试',
        'criterion': '100 次复位后身份恢复、无新增内核错误且每轮成功；会短暂断开 USB。',
    },
}


HUB_RESET = Path('/sys/class/leds/usb_hub_reset/brightness')
REPORT_ROOT = Path('/var/lib/robopi-tui/reports/usb-stress')
KERNEL_ERRORS = re.compile(r'oops|panic|call trace|bug:', re.IGNORECASE)
USB_ADDRESS = re.compile(r'^Bus \d+ Device \d+: ')


class TestInterrupted(Exception):
    pass


def stop_on_signal(signum, frame):
    raise TestInterrupted(f'Signal {signum} interrupted USB stress test')


def collect():
    outputs = []
    for command in (['lsusb'], ['dmesg']):
        completed = subprocess.run(command, capture_output=True, text=True,
                                   timeout=10, check=True)
        outputs.append(completed.stdout)
    return tuple(outputs)


def device_ids(lsusb_output):
    return sorted(USB_ADDRESS.sub('', line) for line in lsusb_output.splitlines()
                  if line.strip())


def kernel_error_count(dmesg_output):
    return sum(bool(KERNEL_ERRORS.search(line)) for line in dmesg_output.splitlines())


def save_snapshot(directory, lsusb_output, dmesg_output):
    directory.mkdir(mode=0o700)
    (directory / 'lsusb.txt').write_text(lsusb_output, encoding='utf-8')
    (directory / 'dmesg.txt').write_text(dmesg_output, encoding='utf-8')
    try:
        tree = subprocess.run(['lsusb', '-t'], capture_output=True, text=True,
                              timeout=10, check=False)
        (directory / 'lsusb_tree.txt').write_text(tree.stdout + tree.stderr,
                                                  encoding='utf-8')
    except (OSError, subprocess.SubprocessError):
        pass
    devices = sorted(str(path) for pattern in ('ttyUSB*', 'ttyACM*', 'video*')
                     for path in Path('/dev').glob(pattern))
    (directory / 'devices.txt').write_text('\n'.join(devices) + '\n', encoding='utf-8')


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def probe(reset_path=HUB_RESET, report_root=REPORT_ROOT, sample=collect,
          pause=time.sleep, is_root=None, cycles=100, write_reset=None,
          snapshot=save_snapshot):
    if not (os.geteuid() == 0 if is_root is None else is_root()):
        return result('fail', 'USB hub stress test requires root')
    if write_reset is None and not os.access(reset_path, os.W_OK):
        return result('fail', f'USB hub reset is not writable: {reset_path}')
    reset = write_reset or (lambda value: reset_path.write_text(str(value), encoding='ascii'))
    directory = None
    passed = failed = 0
    verdict = None
    restore_error = None
    old_handlers = {number: signal.getsignal(number) for number in
                    (signal.SIGINT, signal.SIGTERM)}
    try:
        for number in old_handlers:
            signal.signal(number, stop_on_signal)
        report_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        directory = report_root / (datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
                                   + '_' + uuid.uuid4().hex[:8])
        directory.mkdir(mode=0o700)
        before_usb, before_dmesg = sample()
        baseline = device_ids(before_usb)
        if not baseline:
            raise OSError('No USB devices were present before the reset test')
        baseline_errors = kernel_error_count(before_dmesg)
        snapshot(directory / 'initial', before_usb, before_dmesg)
        with (directory / 'result.log').open('w', encoding='utf-8') as log:
            for cycle in range(1, cycles + 1):
                reset(1)
                pause(2)
                reset(0)
                pause(5)
                after_usb, after_dmesg = sample()
                current_ids = device_ids(after_usb)
                current_errors = kernel_error_count(after_dmesg)
                stable = (current_ids == baseline and current_errors <= baseline_errors)
                passed += stable
                failed += not stable
                verdict = 'PASS' if stable else 'FAIL'
                log.write(f'[{timestamp()}] [{cycle:03}] {verdict} '
                          f'devices={len(current_ids)} kernel_errors={current_errors}\n')
                log.flush()
                os.fsync(log.fileno())
                if not stable or cycle % 10 == 0:
                    snapshot(directory / f'cycle_{cycle:03}', after_usb, after_dmesg)
            log.write(f'[{timestamp()}] PASS: {passed} FAIL: {failed}\n')
            log.flush()
            os.fsync(log.fileno())
        verdict = result('pass' if failed == 0 and passed == cycles else 'fail',
                         f'USB hub reset cycles: {passed} passed, {failed} failed',
                         value=passed, unit='cycles',
                         details={'passed_cycles': passed, 'failed_cycles': failed,
                                  'log_directory': str(directory)})
    except (OSError, subprocess.SubprocessError, TestInterrupted) as exc:
        verdict = result('error', f'USB stress test stopped: {exc}',
                         details={'passed_cycles': passed, 'failed_cycles': failed,
                                  'log_directory': str(directory) if directory else None})
    finally:
        try:
            reset(0)
        except OSError as exc:
            restore_error = str(exc)
        for number, handler in old_handlers.items():
            signal.signal(number, handler)
    if restore_error:
        return result('error', f'Could not restore USB hub reset: {restore_error}',
                      details=verdict['details'])
    return verdict


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
