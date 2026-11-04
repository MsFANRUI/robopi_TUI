# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 RoboParty

"""Read-only motor snapshot: parsing and the no-enable/no-send contract."""

from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

from loader import motor_status
from loader import task_protocol as rpc

PLUGIN = runpy.run_path(str(Path(__file__).resolve().parents[2]
                             / 'plugins' / '056-motor_errors.py'))


CONFIG = """\
motors:
  motor_interface: [can0, can1]
  motor_num: [1, 1]
  motor_interface_type: [canfd, canfd]
  motor_type: [LRO, LRO]
  motor_id: [1, 2]
  motor_model: [0, 1]
  motor_zero_offset: [0.5, 0.0]
  master_id_offset: 16
"""

FORBIDDEN = ('init_motor', 'lock_motor', 'refresh_motor_status',
             'clear_motor_error', 'deinit_motor')


class FakeDriver:
    def __init__(self, code):
        self.code = code

    def get_error_id(self):
        return self.code

    def get_motor_pos(self):
        return 0.25

    def get_motor_spd(self):
        return 1.5

    def get_motor_current(self):
        return 2.5

    def get_motor_temperature(self):
        return 33.0

    def __getattr__(self, name):
        if name in FORBIDDEN:
            raise AssertionError(f'forbidden motor call: {name}')
        raise AttributeError(name)


class FakeMotorDriver:
    calls = []

    @classmethod
    def create_motor(cls, *args):
        cls.calls.append(args)
        return FakeDriver(0x03 if args[0] == 1 else 0x00)


class MotorStatusTests(unittest.TestCase):
    def setUp(self):
        FakeMotorDriver.calls = []
        self.temp = tempfile.TemporaryDirectory()
        self.config = Path(self.temp.name) / 'robot.yaml'
        self.config.write_text(CONFIG, encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def test_read_only_snapshot_and_missing_feedback(self):
        counts = {('can0', 1): 3}
        data = motor_status.read(
            config=str(self.config), settle=0, driver_class=FakeMotorDriver,
            feedback_counter=lambda interfaces, seconds: counts,
            now=lambda: '2026-11-03T00:00:00+00:00')
        self.assertEqual(2, len(data['motors']))
        first, second = data['motors']
        self.assertEqual((1, 'canfd', 'can0', 'LRO', 0, 16, 0.5),
                         FakeMotorDriver.calls[0])
        self.assertTrue(first['feedback'])
        self.assertEqual(0x03, first['error'])
        self.assertEqual('LRO_UNDER_VOLTAGE', first['errorName'])
        self.assertEqual(33.0, first['temperature'])
        self.assertFalse(second['feedback'])
        self.assertIsNone(second['error'])
        self.assertIsNone(second['errorName'])
        self.assertIn('motor 2: no feedback', ' '.join(data['warnings']))
        self.assertEqual('robopi-tui', data['server'])

    def test_missing_config_is_reported(self):
        with self.assertRaises(FileNotFoundError):
            motor_status.read(config='/nonexistent/robot.yaml')


class PluginTests(unittest.TestCase):
    def snapshot(self, motors):
        return {'config': '/x/robot.yaml', 'settleSeconds': 0.8,
                'motors': motors, 'warnings': []}

    def test_no_errors_pass(self):
        data = self.snapshot([{'id': 1, 'feedback': True, 'error': 0,
                               'errorName': 'LRO_NO_ERROR'}])
        self.assertEqual('pass', PLUGIN['probe'](read=lambda _: data)['status'])

    def test_error_fails(self):
        data = self.snapshot([{'id': 2, 'feedback': True, 'error': 3,
                               'errorName': 'LRO_UNDER_VOLTAGE'}])
        result = PLUGIN['probe'](read=lambda _: data)
        self.assertEqual('fail', result['status'])
        self.assertIn('LRO_UNDER_VOLTAGE', result['message'])

    def test_missing_feedback_needs_review(self):
        data = self.snapshot([{'id': 3, 'feedback': False, 'error': None,
                               'errorName': None}])
        self.assertEqual('needs_review', PLUGIN['probe'](read=lambda _: data)['status'])


class ProtocolTests(unittest.TestCase):
    def test_motors_get_uses_optional_config(self):
        with patch.object(rpc.runtime, 'motor_status', return_value={'motors': []}) as call:
            response = rpc.dispatch({'jsonrpc': '2.0', 'id': 'x', 'method': 'motors.get',
                                     'params': {'config': '/tmp/robot.yaml'}})
        self.assertEqual({'motors': []}, response['result'])
        call.assert_called_once_with('/tmp/robot.yaml')


if __name__ == '__main__':
    unittest.main()
