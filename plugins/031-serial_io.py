#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Run a bounded serial receive, transmit, loopback or two-port test."""

import json
from pathlib import Path
import re
import select
import subprocess
import termios

from loader.plugin_helpers import plugin_params, read_text, result


PLUGIN = {
    'id': 'RP031',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Serial I/O test',
    'version': '1.0',
    'lifecycle': 'testing',
    'kind': 'test',
    'category': 'Serial',
    'batch': False,
    'safety': 'active',
    'confirm': 'Check wiring and ensure neither port is owned by a console or service. Continue?',
    'inputs': [
        {
            'name': 'mode',
            'label': 'Test mode',
            'type': 'choice',
            'choices': ['receive', 'send', 'loopback', 'crosstalk'],
            'required': True,
        },
        {
            'name': 'port',
            'label': 'Serial port',
            'type': 'text',
            'pattern': 'tty(?:S|AMA|USB|ACM)[0-9]+',
            'required': True,
        },
        {
            'name': 'other_port',
            'label': 'Other port for crosstalk',
            'type': 'text',
            'pattern': 'tty(?:S|AMA|USB|ACM)[0-9]+',
            'required': True,
            'when': {'mode': 'crosstalk'},
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
            'name': 'payload',
            'label': 'Text to send',
            'type': 'text',
            'pattern': '[^\\r\\n]{1,64}',
            'default': 'ROBOPI_LOOPBACK',
        },
    ],
    'timeout_s': 20,
    'documentation': {
        'title': '串口收发/回环/互测',
        'criterion': '有界读写并恢复 termios，禁止内核控制台端口。',
    },
}


PORT_PATTERN = re.compile(r'tty(?:S|AMA|USB|ACM)[0-9]+\Z')


def is_console(name, cmdline=Path('/proc/cmdline'), consoles=Path('/proc/consoles')):
    return (bool(re.search(rf'(?:^|\s)console={re.escape(name)}(?:[,\s]|$)',
                           read_text(cmdline))) or
            bool(re.search(rf'(?m)^{re.escape(name)}\s', read_text(consoles))))


def port_path(name, root=Path('/dev')):
    if not isinstance(name, str) or not PORT_PATTERN.fullmatch(name):
        raise ValueError('Invalid serial port')
    path = root / name
    if not path.is_char_device():
        raise ValueError(f'{path} is not a character device')
    if is_console(name):
        raise ValueError(f'{name} is a kernel console')
    return path


def configure(path, baud):
    completed = subprocess.run(['stty', '-F', str(path), str(baud), 'raw', '-echo',
                                'min', '0', 'time', '1'],
                               capture_output=True, text=True, timeout=2, check=False)
    if completed.returncode:
        raise OSError(completed.stderr.strip() or 'stty failed')


def read_for(stream, seconds):
    ready, _, _ = select.select([stream], [], [], seconds)
    return stream.read(512) if ready else b''


def probe(mode, port, baud=115200, payload='ROBOPI_LOOPBACK', other_port=None):
    if mode not in PLUGIN['inputs'][0]['choices'] or not 1200 <= baud <= 3000000:
        return result('error', 'Invalid mode or baud rate')
    if not isinstance(payload, str) or not re.fullmatch(r'[^\r\n]{1,64}', payload):
        return result('error', 'Invalid transmit text')
    try:
        first = port_path(port)
        second = port_path(other_port) if mode == 'crosstalk' else None
        if mode == 'crosstalk' and (second is None or second == first):
            return result('error', 'Select two different serial ports')
        with first.open('r+b', buffering=0) as a:
            old_a = termios.tcgetattr(a.fileno())
            try:
                configure(first, baud)
                if second:
                    with second.open('r+b', buffering=0) as b:
                        old_b = termios.tcgetattr(b.fileno())
                        try:
                            configure(second, baud)
                            responses = []
                            for source, sink in ((a, b), (b, a)):
                                token = payload.encode()
                                source.write(token + b'\r\n')
                                termios.tcdrain(source.fileno())
                                received = read_for(sink, 3)
                                responses.append({'source': source.name, 'sink': sink.name,
                                                  'received': received.decode(errors='replace'),
                                                  'matched': token in received})
                        finally:
                            termios.tcsetattr(b.fileno(), termios.TCSANOW, old_b)
                    return result('pass' if all(item['matched'] for item in responses) else 'fail',
                                  'Two-port serial crosstalk checked',
                                  details={'directions': responses})
                if mode == 'receive':
                    received = read_for(a, 5)
                    return result('needs_review' if received else 'fail',
                                  f'Received {len(received)} byte(s) in 5 seconds',
                                  value=len(received), unit='bytes',
                                  details={'data': received.decode(errors='replace')})
                token = payload.encode()
                a.write(token + b'\r\n')
                termios.tcdrain(a.fileno())
                if mode == 'send':
                    return result('needs_review', 'Text sent; peer receipt requires confirmation',
                                  value=len(token), unit='bytes')
                received = read_for(a, 3)
                return result('pass' if token in received else 'fail',
                              'Serial loopback matched' if token in received else
                              'Serial loopback did not match',
                              details={'received': received.decode(errors='replace')})
            finally:
                termios.tcsetattr(a.fileno(), termios.TCSANOW, old_a)
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return result('error', str(exc))


if __name__ == '__main__':
    print(json.dumps(probe(**plugin_params()), ensure_ascii=False))
