# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Plugin metadata edits must be validated before touching installed sources."""

import json
from pathlib import Path
import runpy
import tempfile
import unittest
from unittest.mock import patch

from loader.plugin_catalog import load_plugins
from loader.plugin_metadata import manage_plugins, replace_field, set_field


ROOT = Path(__file__).resolve().parents[2]
APP = runpy.run_path(str(ROOT / 'TUI' / 'robopi-tui'))


def fixture(directory):
    script = directory / '001-fixture.py'
    script.write_text(
        "PLUGIN = {\n"
        "    'id': 'RP001',\n"
        "    'station': ['robopi2', 'rdkx5', 'opi5pro'],\n"
        "    'clients': ['tui', 'csharp'],\n"
        "    'author': 'wentywenty',\n"
        "    'name': '温度检查',\n"
        "    'documentation': {'title': '温度检查', 'criterion': '温度低于阈值'},\n"
        "    'version': '1.0',\n"
        "    'lifecycle': 'testing',\n"
        "    'safety': 'passive',\n"
        "    'depends_on': [],\n"
        "}\n"
        "# Keep plugin behavior unchanged.\n"
        "raise RuntimeError('metadata inspection executed plugin code')\n",
        encoding='utf-8')
    return script


class PluginManagerTests(unittest.TestCase):
    def test_updates_literal_value_and_preserves_code(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            script = fixture(directory)
            with patch('loader.plugin_metadata.os.geteuid', return_value=0):
                set_field('RP001', 'lifecycle', 'official', directory)
                set_field('RP001', 'inputs', [
                    {'name': 'port', 'label': 'Port', 'type': 'text', 'required': True}
                ], directory)
            metadata = load_plugins(directory)[0]
            self.assertEqual(metadata['lifecycle'], 'official')
            self.assertEqual(metadata['inputs'][0]['name'], 'port')
            self.assertIn("'name': '温度检查'", script.read_text())
            self.assertIn('# Keep plugin behavior unchanged.', script.read_text())

    def test_invalid_edits_do_not_change_source(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            script = fixture(directory)
            original = script.read_text()
            with patch('loader.plugin_metadata.os.geteuid', return_value=0):
                for field, value in [('id', 'RP002'), ('lifecycle', 'unknown'),
                                     ('depends_on', ['RP001']), ('timeout_s', 31)]:
                    with self.subTest(field=field), self.assertRaises(ValueError):
                        set_field('RP001', field, value, directory)
                    self.assertEqual(script.read_text(), original)

    def test_edit_requires_root_and_rejects_bad_json_types(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            script = fixture(directory)
            with patch('loader.plugin_metadata.os.geteuid', return_value=1000):
                with self.assertRaises(PermissionError):
                    set_field('RP001', 'lifecycle', 'official', directory)
            with patch('loader.plugin_metadata.os.geteuid', return_value=0):
                with self.assertRaises(ValueError):
                    set_field('RP001', 'inputs', {'name': 'wrong type'}, directory)
            self.assertEqual(load_plugins(directory)[0]['lifecycle'], 'testing')
            self.assertIn("'safety': 'passive'", script.read_text())

    def test_replaces_value_with_utf8_before_it(self):
        with tempfile.TemporaryDirectory() as temp:
            source = fixture(Path(temp)).read_text()
            changed = replace_field(source, '001-fixture.py', 'lifecycle', 'deprecated')
            self.assertIn("'name': '温度检查'", changed)
            self.assertIn("'lifecycle': 'deprecated'", changed)

    def test_tui_can_show_and_edit_json_field(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            fixture(directory)

            class FakeUI:
                selections = iter(['RP001', 'show', 'field', 'category', None, None])

                def __init__(self):
                    self.shown = None
                    self.messages = []

                def menu(self, *args):
                    return next(self.selections)

                def output(self, title, body):
                    self.shown = json.loads(body)

                def edit(self, title, content):
                    return '"Diagnostics"'

                def yes(self, title, prompt):
                    return True

                def message(self, title, body):
                    self.messages.append((title, body))

            ui = FakeUI()
            with patch('loader.plugin_metadata.os.geteuid', return_value=0):
                manage_plugins(ui, directory)
            self.assertEqual(ui.shown['lifecycle'], 'testing')
            self.assertNotIn('_script', ui.shown)
            self.assertEqual(load_plugins(directory)[0]['category'], 'Diagnostics')
            self.assertIn(('Plugin updated', 'RP001.category updated.'), ui.messages)

    def test_tui_can_change_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            fixture(directory)

            class FakeUI:
                selections = iter(['RP001', 'lifecycle', 'deprecated', None, None])

                def menu(self, *args):
                    return next(self.selections)

                def yes(self, title, prompt):
                    self.prompt = prompt
                    return True

                def message(self, title, body):
                    pass

            ui = FakeUI()
            with patch('loader.plugin_metadata.os.geteuid', return_value=0):
                manage_plugins(ui, directory)
            self.assertEqual(load_plugins(directory)[0]['lifecycle'], 'deprecated')
            self.assertIn('testing -> deprecated', ui.prompt)

    def test_main_menu_exposes_manager(self):
        class FakeUI:
            selections = iter(['manager', None])

            def menu(self, title, items, prompt=''):
                self.items = items
                return next(self.selections)

        ui = FakeUI()
        called = []
        with patch.dict(APP['main_menu'].__globals__,
                        {'load_catalog': lambda develop=False: [],
                         'manage_plugins': lambda user_interface: called.append(user_interface)}):
            APP['main_menu'](ui)
        self.assertIn(('manager', 'Plugin metadata'), ui.items)
        self.assertEqual(called, [ui])


if __name__ == '__main__':
    unittest.main()
