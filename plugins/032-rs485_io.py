#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Bounded RS485 send or receive with optional GPIO direction control."""

import json
from pathlib import Path
import re
import select
import subprocess
import termios
import time

from loader.plugin_helpers import plugin_params, read_text, result


PLUGIN = {
    'id': 'RP032',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'RS485 I/O test',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'test',
    'category': 'Serial',
    'batch': False,
    'safety': 'active',
    'confirm': 'Confirm the RS485 port, direction pin and external wiring. Continue?',
    'inputs': [
        {
            'name': 'mode',
            'label': 'Test mode',
            'type': 'choice',
            'choices': ['receive', 'send'],
            'required': True,
        },
        {
            'name': 'port',
            'label': 'RS485 serial port',
            'type': 'text',
            'pattern': 'tty(?:USB|S|AMA)[0-9]+',
            'required': True,
        },
        {
            'name': 'baud',
            'label': 'Baud rate',
            'type': 'integer',
            'minimum': 1200,
            'maximum': 3000000,
            'default': 115200,
        },
        {
            'name': 'gpio',
            'label': 'Optional RE/DE GPIO number',
            'type': 'integer',
            'minimum': 0,
            'maximum': 4095,
        },
        {
            'name': 'payload',
            'label': 'Text to send',
            'type': 'text',
            'pattern': '[^\\r\\n]{1,64}',
            'default': 'ROBOPI_RS485',
            'when': {'mode': 'send'},
        },
    ],
    'timeout_s': 15,
    'documentation': {
        'title': 'RS485 收发',
        'criterion': '有界收发，可指定收发方向 GPIO。',
    },
}


def probe(mode, port, baud=115200, gpio=None, payload='ROBOPI_RS485',
          dev_root=Path('/dev'), gpio_root=Path('/sys/class/gpio')):
    if mode not in ('receive', 'send') or not re.fullmatch(r'tty(?:USB|S|AMA)[0-9]+', port):
        return result('error', 'Invalid RS485 mode or port')
    if type(baud) is not int or not 1200 <= baud <= 3000000:
        return result('error', 'Invalid baud rate')
    if mode == 'send' and (not isinstance(payload, str)
                           or not re.fullmatch(r'[^\r\n]{1,64}', payload)):
        return result('error', 'Invalid transmit text')
    dev = dev_root / port
    if not dev.is_char_device():
        return result('fail', f'{dev} is not a serial device')
    if re.search(rf'(?:^|\s)console={re.escape(port)}(?:[,\s]|$)',
                 read_text('/proc/cmdline')):
        return result('fail', f'{port} is a kernel console')
    direction = None
    previous = None
    exported = False
    try:
        if gpio is not None:
            if type(gpio) is not int or not 0 <= gpio <= 4095:
                return result('error', 'Invalid direction GPIO')
            direction = gpio_root / f'gpio{gpio}'
            if not direction.is_dir():
                (gpio_root / 'export').write_text(str(gpio) + '\n')
                exported = True
            previous = (read_text(direction / 'direction'), read_text(direction / 'value'))
            (direction / 'direction').write_text('out\n')
            (direction / 'value').write_text('1\n' if mode == 'send' else '0\n')
            if mode == 'send':
                time.sleep(0.02)
        with dev.open('r+b', buffering=0) as stream:
            saved = termios.tcgetattr(stream.fileno())
            try:
                configured = subprocess.run(['stty', '-F', str(dev), str(baud), 'raw',
                                             '-echo', 'min', '0', 'time', '1'],
                                            capture_output=True, text=True,
                                            timeout=2, check=False)
                if configured.returncode:
                    raise OSError(configured.stderr.strip() or 'stty failed')
                if mode == 'send':
                    data = payload.encode() + b'\r\n'
                    stream.write(data)
                    termios.tcdrain(stream.fileno())
                    return result('needs_review', 'RS485 data sent; peer receipt requires confirmation',
                                  value=len(data), unit='bytes',
                                  details={'port': port, 'baud': baud, 'gpio': gpio})
                ready, _, _ = select.select([stream], [], [], 5)
                data = stream.read(512) if ready else b''
                return result('needs_review' if data else 'fail',
                              f'Received {len(data)} RS485 byte(s) in 5 seconds',
                              value=len(data), unit='bytes',
                              details={'port': port, 'baud': baud, 'gpio': gpio,
                                       'data': data.decode(errors='replace')})
            finally:
                termios.tcsetattr(stream.fileno(), termios.TCSANOW, saved)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))
    finally:
        if direction is not None:
            try:
                if exported:
                    (gpio_root / 'unexport').write_text(str(gpio) + '\n')
                elif previous:
                    (direction / 'value').write_text(previous[1] + '\n')
                    (direction / 'direction').write_text(previous[0] + '\n')
            except OSError as exc:
                return result('error', f'Could not restore RS485 direction GPIO: {exc}')


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
