# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 RoboParty

"""Board serial detection and identity/snapshot exposure."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import uuid

from loader import board_backend
from loader import board_snapshot
from loader import task_runtime


class BoardSerialTests(unittest.TestCase):
    def test_device_tree_wins(self):
        with tempfile.TemporaryDirectory() as temp:
            tree = Path(temp) / 'serial-number'
            cpuinfo = Path(temp) / 'cpuinfo'
            tree.write_text('ROBOPI-SN-001\x00')
            cpuinfo.write_text('Serial\t: CPU-SN')
            self.assertEqual(('ROBOPI-SN-001', 'device-tree'),
                             board_snapshot.board_serial(tree, cpuinfo))

    def test_cpuinfo_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            tree = Path(temp) / 'missing'
            cpuinfo = Path(temp) / 'cpuinfo'
            cpuinfo.write_text('processor\t: 0\nSerial\t\t: CPU-SN-002\n')
            self.assertEqual(('CPU-SN-002', 'cpuinfo'),
                             board_snapshot.board_serial(tree, cpuinfo))

    def test_missing_serial_is_empty(self):
        with tempfile.TemporaryDirectory() as temp:
            tree = Path(temp) / 'missing'
            cpuinfo = Path(temp) / 'cpuinfo'
            cpuinfo.write_text('processor\t: 0\n')
            self.assertEqual(('', ''), board_snapshot.board_serial(tree, cpuinfo))

    def test_identity_includes_serial(self):
        values = {'/etc/machine-id': 'machine', '/proc/sys/kernel/random/boot_id': 'boot',
                  '/etc/hostname': 'host'}
        with patch.object(board_snapshot, 'board_serial', return_value=('SN-003', 'device-tree')), \
                patch.object(board_snapshot, 'text', side_effect=lambda path, optional=False: values.get(path, '')), \
                patch.object(board_snapshot.os, 'geteuid', return_value=0):
            identity = board_snapshot.identity()
        self.assertEqual('SN-003', identity['serial'])
        self.assertEqual('device-tree', identity['serialSource'])
        self.assertEqual('machine', identity['machineId'])


class SerialBindingTests(unittest.TestCase):
    def make_job(self, root, identity):
        job_id = str(uuid.uuid4())
        directory = root / job_id
        directory.mkdir()
        task_runtime.atomic_json(directory / 'state.json', dict(
            apiVersion=1, jobId=job_id, state='completed', identity=identity))
        return job_id

    def test_serial_conflict_rejects_old_result(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job_id = self.make_job(root, dict(machineId='m', bootId='b', serial='SN-A'))
            with patch.object(task_runtime.backend.board_snapshot, 'identity',
                              return_value=dict(machineId='m', bootId='b', serial='SN-B')):
                with self.assertRaises(task_runtime.JobError) as raised:
                    task_runtime.read_status(root, job_id)
            self.assertEqual('BOARD_SERIAL_MISMATCH', raised.exception.code)

    def test_missing_serial_falls_back_to_machine_id(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            job_id = self.make_job(root, dict(machineId='m', bootId='b', serial='SN-A'))
            with patch.object(task_runtime.backend.board_snapshot, 'identity',
                              return_value=dict(machineId='m', bootId='b', serial='')):
                state = task_runtime.read_status(root, job_id)
            self.assertEqual('completed', state['state'])


class SnapshotSerialTests(unittest.TestCase):
    def test_snapshot_has_serial_row(self):
        identity = {'hostname': 'board', 'uid': 0, 'serial': 'SN-004',
                    'serialSource': 'device-tree'}
        raw = dict(identity=identity, endIdentity=dict(identity), collectedAt='now')
        for name in ('system', 'resources', 'network', 'usb', 'can', 'udev',
                     'firmware', 'sources', 'services'):
            raw[name] = dict(data=[], error=None)
        raw['packages'] = dict(data=dict(items=[]), error=None)
        with patch.object(board_backend.board_snapshot, 'collect', return_value=raw):
            data = board_backend.snapshot()
        row = next(item for item in data['parameters'] if item['name'] == '板卡序列号')
        self.assertEqual('SN-004', row['value'])
        self.assertEqual('pass', row['outcome'])


if __name__ == '__main__':
    unittest.main()
