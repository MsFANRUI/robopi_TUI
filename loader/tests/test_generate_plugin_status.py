# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""The published status table must follow plugin metadata changes."""

from copy import deepcopy
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest

from loader.generate_plugin_status import STATUS, main, render_status
from loader.plugin_catalog import load_plugins


TEMP_ROOT = Path(__file__).resolve().parents[4] / 'test' / 'tmp'


class PluginStatusTests(unittest.TestCase):
    def test_published_status_matches_all_plugins(self):
        plugins = load_plugins()
        content = render_status(plugins)
        self.assertEqual(content, STATUS.read_text(encoding='utf-8'))
        self.assertEqual(sum(line.startswith('| RP') for line in content.splitlines()),
                         len(plugins))

    def test_documentation_changes_rendered_status_and_stale_check(self):
        plugin = deepcopy(load_plugins()[0])
        plugin['documentation']['criterion'] = '新的验证判据。'
        plugin['version'] = '1.1'
        self.assertIn('新的验证判据。', render_status([plugin]))
        self.assertIn('| RP001 | 1.1 |', render_status([plugin]))
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as temp:
            output = Path(temp) / 'STATUS.md'
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                self.assertEqual(main(['--write', '--output', str(output)]), 0)
                self.assertEqual(main(['--check', '--output', str(output)]), 0)
                output.write_text('outdated', encoding='utf-8')
                self.assertEqual(main(['--check', '--output', str(output)]), 1)


if __name__ == '__main__':
    unittest.main()
