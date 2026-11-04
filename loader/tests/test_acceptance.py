# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 RoboParty

"""Per-serial acceptance records."""

import json
from pathlib import Path
import tempfile
import unittest

from loader import acceptance


class AcceptanceTests(unittest.TestCase):
    def test_serial_key_and_record(self):
        with tempfile.TemporaryDirectory() as temp:
            target = acceptance.write(
                Path(temp), 'plugin', 'run-1',
                {'machineId': 'm', 'serial': 'SN/1'},
                {'outcome': 'pass'}, '2026-11-03T00:00:00+00:00')
            self.assertEqual('sn-SN_1', target.parent.name)
            self.assertTrue(target.name.endswith('_run-1.json'))
            self.assertEqual(0, target.parent.stat().st_mode & 0o077)
            record = json.loads(target.read_text(encoding='utf-8'))
            self.assertEqual('plugin', record['kind'])
            self.assertEqual({'outcome': 'pass'}, record['payload'])
            self.assertEqual('SN/1', record['identity']['serial'])

    def test_machine_id_fallback(self):
        with tempfile.TemporaryDirectory() as temp:
            target = acceptance.write(
                Path(temp), 'job', 'job-1',
                {'machineId': 'machine/one', 'serial': ''}, {'outcome': 'pass'})
            self.assertEqual('machine-machine_one', target.parent.name)

    def test_unknown_identity_falls_back(self):
        with tempfile.TemporaryDirectory() as temp:
            target = acceptance.write(Path(temp), 'job', 'job-2', {}, {})
            self.assertEqual('machine-unknown', target.parent.name)


if __name__ == '__main__':
    unittest.main()
