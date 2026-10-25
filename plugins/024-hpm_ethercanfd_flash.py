#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Flash the packaged EtherCANFD firmware with roboparty-analyze's tool."""

import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP024',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Flash HPM EtherCANFD',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'active',
    'category': 'Interfaces',
    'confirm': 'Erase and write HPM flash using the packaged EtherCANFD image?',
    'requires': [],
    'depends_on': ['RP001'],
    'timeout_s': 930,
    'documentation': {
        'title': 'HPM EtherCANFD 刷写',
        'criterion': '唯一非空打包固件存在且刷写成功；不包含读回或重启验证。',
    },
}


FLASHER = Path('/opt/roboparty/bin/flash_hpm.sh')
FIRMWARE_DIR = Path('/opt/roboparty/lib/firmware')


def run_flash(flasher, firmware):
    process = subprocess.Popen([str(flasher), str(firmware)], stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        output, _ = process.communicate(timeout=900)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.communicate()
        raise
    return subprocess.CompletedProcess(process.args, process.returncode, output, '')


def probe(flasher=FLASHER, firmware_dir=FIRMWARE_DIR, execute=run_flash, is_root=None):
    firmware_files = sorted(firmware_dir.glob('ethercanfd_*.bin'))
    if not flasher.is_file() or not os.access(flasher, os.X_OK):
        return result('fail', 'roboparty-analyze HPM flasher is missing or not executable')
    if len(firmware_files) != 1:
        return result('fail', f'Expected one packaged EtherCANFD image; found {len(firmware_files)}',
                      details={'firmware_files': [str(path) for path in firmware_files]})
    firmware = firmware_files[0]
    if not firmware.is_file() or firmware.stat().st_size == 0:
        return result('fail', 'Packaged EtherCANFD image is empty or unreadable')
    if not (os.geteuid() == 0 if is_root is None else is_root()):
        return result('fail', 'HPM flashing requires root')
    try:
        digest_state = hashlib.sha256()
        with firmware.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                digest_state.update(chunk)
        digest = digest_state.hexdigest()
        completed = execute(flasher, firmware)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', f'HPM flash command failed: {exc}',
                      details={'firmware': str(firmware)})
    details = {'firmware': str(firmware), 'sha256': digest,
               'exit_code': completed.returncode, 'flash_log': completed.stdout[-16000:]}
    if completed.returncode:
        return result('fail', 'HPM erase/write command failed', details=details)
    return result('pass', 'HPM erase/write command completed; no readback verification',
                  details=details)


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
