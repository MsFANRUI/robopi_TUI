#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Read the BMS firmware version from its current service or broadcast frame."""

import json
from pathlib import Path
import re
import shlex
import socket
import struct
import subprocess
import time

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP022',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui', 'csharp'],
    'author': 'wentywenty',
    'name': 'BMS firmware version',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'passive',
    'category': 'BMS',
    'requires': [],
    'depends_on': ['RP021'],
    'timeout_s': 15,
    'documentation': {
        'title': 'BMS 固件版本',
        'criterion': '按 `BMS_TYPE` 读到非零固件/硬件版本；不比较目标版本。',
    },
}


CONFIG = Path('/etc/default/bms_daemon')
VERSION_ID = 0x18F00903
VERSION_LINE = re.compile(r'FW Version: 0x([0-9a-fA-F]+)\s*\|\s*HW Version: 0x([0-9a-fA-F]+)')


def current_service_log():
    invocation = subprocess.run(
        ['systemctl', 'show', '--property=InvocationID', '--value', 'bms.service'],
        capture_output=True, text=True, timeout=3, check=True).stdout.strip()
    if not re.fullmatch(r'[0-9a-fA-F]{32}', invocation):
        return ''
    return subprocess.run(['journalctl', f'_SYSTEMD_INVOCATION_ID={invocation}',
                           '--no-pager', '-o', 'cat'], capture_output=True,
                          text=True, timeout=3, check=True).stdout


def read_can_version(port):
    with socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW) as bus:
        bus.bind((port,))
        deadline = time.monotonic() + 5
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError('No GFCAN BMS version frame within 5 seconds')
            bus.settimeout(remaining)
            frame = bus.recv(16)
            if len(frame) < 16:
                continue
            can_id, size, data = struct.unpack('=IB3x8s', frame)
            if (can_id & 0x80000000 and not can_id & 0x60000000
                    and can_id & 0x1FFFFFFF == VERSION_ID and size >= 6):
                return data


def probe(config=CONFIG, query_log=current_service_log, listen=read_can_version):
    try:
        settings = {}
        for line in config.read_text(encoding='utf-8').splitlines():
            key, separator, raw = line.partition('=')
            if separator and key.strip() in ('BMS_TYPE', 'BMS_PORT'):
                values = shlex.split(raw, comments=True)
                if len(values) == 1:
                    settings[key.strip()] = values[0]
        kind = settings.get('BMS_TYPE')
        if kind == 'GFCAN':
            port = settings.get('BMS_PORT', '')
            if not re.fullmatch(r'[A-Za-z0-9_.:-]{1,32}', port):
                return result('fail', 'Configured GFCAN interface is invalid')
            data = listen(port)
            if len(data) < 6:
                return result('fail', 'GFCAN BMS version frame is incomplete')
            software = '.'.join(str(part) for part in data[:3])
            hardware = '.'.join(str(part) for part in data[3:6])
            has_version = any(data[:6])
            source = f'{port} CAN frame 0x{VERSION_ID:08X}'
        elif kind in ('TWS', 'GF', 'SCUD485'):
            versions = VERSION_LINE.findall(query_log())
            if not versions:
                return result('fail', 'No BMS version in the current bms.service invocation')
            software_raw, hardware_raw = (int(value, 16) for value in versions[-1])
            software, hardware = f'0x{software_raw:04X}', f'0x{hardware_raw:04X}'
            has_version = bool(software_raw or hardware_raw)
            source = 'current bms.service invocation'
        else:
            return result('skip', f'BMS_TYPE {kind or "unset"} has no supported version source')
    except FileNotFoundError:
        return result('fail', 'BMS configuration is missing')
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return result('error', f'Could not read BMS version: {exc}')
    if not has_version:
        return result('fail', 'BMS reported zero firmware and hardware versions')
    return result('pass', f'BMS firmware version {software}',
                  details={'software_version': software,
                           'hardware_version': hardware, 'source': source})


if __name__ == '__main__':
    print(json.dumps(probe(), ensure_ascii=False))
