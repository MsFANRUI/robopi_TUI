#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Write and verify one LRO motor's limits through motors_py."""

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import uuid

import yaml

from loader.plugin_helpers import result


PLUGIN = {
    'id': 'RP025',
    'station': ['robopi2', 'rdkx5', 'opi5pro'],
    'clients': ['tui'],
    'author': 'wentywenty',
    'name': 'Program one LRO motor parameters',
    'version': '1.0',
    'lifecycle': 'testing',
    'safety': 'active',
    'category': 'Motor',
    'batch': False,
    'confirm': 'Confirm one isolated motor, exclusive CAN ownership, current limit, emergency stop and on-site supervision. Preserve CAN timeout?',
    'inputs': [
        {
            'name': 'config',
            'label': 'Absolute robot.yaml path',
            'type': 'text',
            'pattern': '/[^\n]+',
            'required': True,
            'default': '/opt/roboparty/share/roboparty_inference/robots/rp1/robot.yaml',
        },
        {
            'name': 'interface',
            'label': 'CAN interface',
            'type': 'text',
            'pattern': 'can[0-9]+',
            'required': True,
        },
        {
            'name': 'motor_id',
            'label': 'Motor ID',
            'type': 'integer',
            'minimum': 1,
            'maximum': 2047,
            'required': True,
        },
        {
            'name': 'isolated',
            'label': 'Motor isolated and supervised',
            'type': 'boolean',
            'required': True,
        },
    ],
    'requires': ['can'],
    'depends_on': ['RP001'],
    'timeout_s': 120,
    'documentation': {
        'title': '单台 LRO 电机参数刷写',
        'criterion': '选择并隔离一台电机，逐项读回且 `CAN_TIMEOUT` 不变；不验证断电保持。',
    },
}


# Values match test/deploy_motorlro_params.py; CAN_TIMEOUT is read but never written.
MODEL_PARAMS = {
    0: {'kp': 500.0, 'kd': 50.0, 'pos': 12.5, 'spd': 21.0, 'tor': 36.0},
    1: {'kt': 1.86, 'kp': 500.0, 'kd': 50.0, 'pos': 12.5, 'spd': 21.89, 'tor': 35.3},
    2: {'kt': 2.22, 'kp': 500.0, 'kd': 50.0, 'pos': 12.5, 'spd': 16.13, 'tor': 56.5},
    3: {'kt': 2.44, 'kp': 500.0, 'kd': 50.0, 'pos': 12.5, 'spd': 14.24, 'tor': 141.7},
}
SIGNED = {'pos', 'spd', 'tor'}
KEYS = ('kt', 'kp', 'kd', 'pos', 'spd', 'tor')
JOURNAL_DIR = Path('/var/lib/robopi-tui/reports/motor-params')


def select_target(path, interface, motor_id):
    config = yaml.safe_load(path.read_text(encoding='utf-8'))
    motors = config.get('motors') if isinstance(config, dict) else None
    if not isinstance(motors, dict):
        raise ValueError('robot.yaml has no motors mapping')
    names = motors.get('motor_interface')
    counts = motors.get('motor_num')
    types = motors.get('motor_type')
    protocols = motors.get('motor_interface_type')
    ids = motors.get('motor_id')
    models = motors.get('motor_model')
    if not all(isinstance(value, list) for value in (names, counts, types,
                                                     protocols, ids, models)):
        raise ValueError('robot.yaml motor arrays are incomplete')
    if not len(names) == len(counts) == len(types) == len(protocols):
        raise ValueError('robot.yaml motor bus arrays have different lengths')
    if any(type(count) is not int or count < 0 for count in counts):
        raise ValueError('robot.yaml motor counts are invalid')
    if len(ids) != sum(counts) or len(models) != len(ids):
        raise ValueError('robot.yaml motor IDs and models do not match bus counts')
    matches = []
    offset = 0
    for name, count, kind, protocol in zip(names, counts, types, protocols):
        if name == interface:
            matches.extend((kind, protocol, models[index])
                           for index in range(offset, offset + count)
                           if ids[index] == motor_id)
        offset += count
    if (len(matches) != 1 or matches[0][0] != 'LRO'
            or matches[0][1] not in ('canfd', 'ethercanfd')
            or type(matches[0][2]) is not int or matches[0][2] not in MODEL_PARAMS):
        raise ValueError('Select one configured LRO CAN-FD motor with a known model')
    return matches[0][2]


def link_ready(interface):
    completed = subprocess.run(['ip', '-j', '-details', 'link', 'show', 'dev', interface],
                               capture_output=True, text=True, timeout=3, check=True)
    links = json.loads(completed.stdout)
    if len(links) != 1 or 'UP' not in links[0].get('flags', []):
        raise ValueError(f'{interface} is not UP')
    can = (links[0].get('linkinfo') or {}).get('info_data') or {}
    if can.get('state') != 'ERROR-ACTIVE':
        raise ValueError(f'{interface} CAN state is {can.get("state")}')
    nominal = (can.get('bittiming') or {}).get('bitrate')
    data = (can.get('data_bittiming') or {}).get('bitrate')
    if links[0].get('mtu') != 72 or nominal != 1000000 or data != 5000000:
        raise ValueError(f'{interface} must be CAN-FD at 1000000/5000000 bit/s')
    return {'state': can['state'], 'bitrate': nominal, 'data_bitrate': data}


def make_session(interface, motor_id, model):
    site = (Path('/opt/roboparty/lib') /
            f'python{sys.version_info.major}.{sys.version_info.minor}' / 'site-packages')
    sys.path.insert(0, str(site))
    from motors_py import LroParamSession
    return LroParamSession(interface, motor_id, model)


def expected_range(key, maximum):
    return (-maximum if key in SIGNED else 0.0, maximum)


def close_enough(actual, expected):
    return abs(actual - expected) < max(0.001, abs(expected) * 0.01 + 0.001)


def record(path, event, **fields):
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'event': event, 'time_ns': time.time_ns(), **fields}) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


def probe(config, interface, motor_id, isolated, session_factory=make_session,
          check_link=link_ready, is_root=None, journal_dir=JOURNAL_DIR,
          pause=time.sleep):
    if not isolated:
        return result('fail', 'Single-motor isolation and supervision were not confirmed')
    if not (os.geteuid() == 0 if is_root is None else is_root()):
        return result('fail', 'Motor parameter flashing requires root')
    if not re.fullmatch(r'can[0-9]+', interface or '') or type(motor_id) is not int:
        return result('fail', 'A CAN interface and one numeric motor ID are required')
    if motor_id < 1 or motor_id > 0x7FF:
        return result('fail', 'Motor ID must be 1..2047')
    if not config or not config.is_absolute():
        return result('fail', 'An absolute robot.yaml path is required')
    details = {'config': str(config), 'interface': interface, 'motor_id': motor_id,
               'isolation_confirmed': True, 'completed_writes': []}
    journal = None
    try:
        model = select_target(config, interface, motor_id)
        details['model'] = model
        details['link'] = check_link(interface)
        session = session_factory(interface, motor_id, model)
        params = MODEL_PARAMS[model]
        before = {key: session.read_param(key) for key in KEYS if key in params}
        timeout_before = session.read_param('can_timeout')
        details['before'] = before
        details['can_timeout_before_ms'] = timeout_before[1]
        journal_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if journal_dir.is_symlink() or journal_dir.stat().st_mode & 0o077:
            raise OSError(f'Motor journal directory is not private: {journal_dir}')
        journal = journal_dir / f'{uuid.uuid4()}.jsonl'
        with journal.open('x', encoding='utf-8') as stream:
            os.fchmod(stream.fileno(), 0o600)
        details['journal'] = str(journal)
        record(journal, 'preflight', target={key: details[key]
                                           for key in ('config', 'interface', 'motor_id', 'model')},
               before=before, can_timeout_ms=timeout_before[1])
        for key in KEYS:
            if key not in params:
                continue
            expected = expected_range(key, params[key])
            record(journal, 'write_started', key=key, expected=expected)
            session.write_param(key, *expected)
            pause(0.1)
            actual = session.read_param(key)
            record(journal, 'readback', key=key, actual=actual)
            details['completed_writes'].append({'key': key, 'expected': expected,
                                                'readback': actual})
            if not all(close_enough(found, wanted)
                       for found, wanted in zip(actual, expected)):
                record(journal, 'stopped', reason='readback_mismatch', key=key)
                return result('fail', f'{key} readback differs; remaining writes stopped',
                              details=details)
        timeout_after = session.read_param('can_timeout')
        details['can_timeout_after_ms'] = timeout_after[1]
        if timeout_after != timeout_before:
            record(journal, 'stopped', reason='can_timeout_changed')
            return result('fail', 'Motor CAN timeout changed unexpectedly', details=details)
        record(journal, 'complete', written=len(details['completed_writes']),
               can_timeout_ms=timeout_after[1])
    except (ImportError, OSError, ValueError, RuntimeError, yaml.YAMLError,
            subprocess.SubprocessError) as exc:
        if journal is not None:
            try:
                record(journal, 'stopped', reason=str(exc))
            except OSError:
                pass
        status = 'fail' if isinstance(exc, (ValueError, RuntimeError)) else 'error'
        return result(status, f'Motor parameter operation stopped: {exc}', details=details)
    return result('pass', f'LRO motor {motor_id} on {interface}: limits written and read back',
                  value=len(details['completed_writes']), unit='parameters', details=details)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--config', type=Path)
    parser.add_argument('--interface')
    parser.add_argument('--motor-id', type=int)
    parser.add_argument('--isolated', action='store_true')
    parser.add_argument('--params')
    parser.add_argument('--params-stdin', action='store_true')
    args = parser.parse_args()
    params = (json.loads(sys.stdin.read() if args.params_stdin else args.params)
              if args.params is not None or args.params_stdin else {})
    config = params.get('config', args.config)
    print(json.dumps(probe(Path(config) if config else None,
                           params.get('interface', args.interface),
                           params.get('motor_id', args.motor_id),
                           params.get('isolated', args.isolated)),
                     ensure_ascii=False))
