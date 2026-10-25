# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""The terminal frontend must only present catalog entries and results."""

import runpy
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
APP = runpy.run_path(str(ROOT / 'TUI' / 'robopi-tui'))
OVERLAYS = runpy.run_path(str(ROOT / 'plugins' / '041-device_tree_overlays.py'))
BOOT = runpy.run_path(str(ROOT / 'plugins' / '055-boot_partition_policy.py'))
AUTOLOGIN = runpy.run_path(str(ROOT / 'plugins' / '044-autologin.py'))
WIFI = runpy.run_path(str(ROOT / 'plugins' / '042-wifi_connection.py'))
PROXY = runpy.run_path(str(ROOT / 'plugins' / '050-network_proxy.py'))
JOURNAL = runpy.run_path(str(ROOT / 'plugins' / '049-journal_storage.py'))
BLANKING = runpy.run_path(str(ROOT / 'plugins' / '046-screen_blanking.py'))


class CoreTests(unittest.TestCase):
    def test_package_version_comes_from_changelog(self):
        expected = (ROOT / 'debian' / 'changelog').read_text().splitlines()[0]
        self.assertIn(f"({APP['PACKAGE_VERSION']})", expected)
        completed = subprocess.run([str(ROOT / 'TUI' / 'robopi-tui'), '--version'],
                                   capture_output=True, text=True, check=True)
        self.assertEqual(completed.stdout.strip(), APP['APP_TITLE'])

    def test_frontend_categories_follow_catalog(self):
        class FakeUI:
            def __init__(self):
                self.items = None
                self.selection = ['1', None]

            def menu(self, title, items, prompt=''):
                self.items = items
                return self.selection.pop(0)

        ui = FakeUI()
        tests = [{'name': 'Board temperature', 'category': 'Tests',
                  'lifecycle': 'official'},
                 {'name': 'Serial getty', 'category': 'Serial',
                  'lifecycle': 'official'}]
        with patch.dict(APP['main_menu'].__globals__,
                        {'load_catalog': lambda develop=False: tests,
                         'plugin_tests_menu': lambda ui, category, develop: setattr(
                             ui, 'category', category)}):
            APP['main_menu'](ui)
        self.assertEqual(ui.category, 'Serial')
        self.assertIn(('1', 'Serial'), ui.items)

    def test_developer_mode_exposes_all_catalog_categories(self):
        class FakeUI:
            def __init__(self):
                self.selections = iter(['mode', '0', None])
                self.menus = []

            def menu(self, title, items, prompt=''):
                self.menus.append(items)
                return next(self.selections)

        ui = FakeUI()
        seen = []
        tests = [{'name': 'Experimental check', 'category': 'Diagnostics',
                  'lifecycle': 'testing'},
                 {'name': 'Retired check', 'category': 'Legacy',
                  'lifecycle': 'deprecated'}]
        with patch.dict(APP['main_menu'].__globals__,
                        {'load_catalog': lambda develop=False: tests if develop else [],
                         'plugin_tests_menu': lambda ui, category, develop: seen.append(
                             (category, develop))}):
            APP['main_menu'](ui)
        self.assertEqual(seen, [('Diagnostics', True)])
        self.assertIn(('1', 'Legacy'), ui.menus[1])
        self.assertIn(('all', 'All plugins'), ui.menus[1])

    def test_frontend_has_no_board_config_implementation(self):
        source = (ROOT / 'TUI' / 'robopi-tui').read_text()
        for name in ('set_device.sh', 'systemctl', 'gpioinfo', 'stty', 'ip link',
                     'robopi-config', 'RP025', 'RP018'):
            self.assertNotIn(name, source)

    def test_overlay_selection_only_uses_installed_dtbo(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            config = root / 'armbianEnv.txt'
            overlays = root / 'overlay'
            overlays.mkdir()
            config.write_text('overlay_prefix=rk3588\noverlays=spi1\nfoo=bar\n')
            (overlays / 'rk3588-spi1.dtbo').touch()
            (overlays / 'rk3588-i2c2.dtbo').touch()
            (overlays / 'other.dtbo').touch()
            found = OVERLAYS['probe']('inspect', config=config, directory=overlays)
            self.assertEqual(set(found['details']['available']), {'spi1', 'i2c2'})
            with patch.object(OVERLAYS['os'], 'geteuid', return_value=0):
                self.assertEqual(OVERLAYS['probe']('set', 'missing', config, overlays)['status'],
                                 'fail')
                changed = OVERLAYS['probe']('set', 'i2c2', config, overlays)
            self.assertEqual(changed['status'], 'pass')
            self.assertIn('foo=bar\n', config.read_text())
            self.assertIn('overlays=i2c2\n', config.read_text())

    def test_boot_partition_policy_preserves_other_mounts(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fstab = root / 'fstab'
            mounts = root / 'mounts'
            fstab.write_text('# board\nUUID=1 / ext4 defaults 0 1\n'
                             'UUID=2 /boot ext4 defaults,ro 0 2\n')
            mounts.write_text('/dev/sda1 / ext4 rw 0 0\n')
            with patch.object(BOOT['os'], 'geteuid', return_value=0):
                observed = BOOT['probe']('writable', fstab, mounts)
            self.assertEqual(observed['status'], 'pass')
            self.assertIn('UUID=1 / ext4 defaults 0 1\n', fstab.read_text())
            self.assertIn('defaults,rw', fstab.read_text())

    def test_lightdm_autologin_stays_inside_seat_section(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            lightdm = root / 'lightdm.conf'
            lightdm.write_text('[Seat:*]\nautologin-user=old\n[LightDM]\nlogind-check-graphical=true\n')
            with patch.object(AUTOLOGIN['os'], 'geteuid', return_value=0), \
                 patch.object(AUTOLOGIN['pwd'], 'getpwnam', return_value=object()):
                observed = AUTOLOGIN['probe']('desktop', 'enable', 'robo', lightdm=lightdm)
            self.assertEqual(observed['status'], 'needs_review')
            self.assertIn('[Seat:*]\nautologin-user=robo\n[LightDM]', lightdm.read_text())

    def test_wifi_secret_stays_out_of_commands_and_profile_is_private(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'net' / 'wlan0' / 'wireless').mkdir(parents=True)
            profiles = root / 'profiles'
            commands = []

            def run(command, **kwargs):
                commands.append(command)
                return subprocess.CompletedProcess(command, 0, '', '')

            with patch.object(WIFI['os'], 'geteuid', return_value=0):
                observed = WIFI['probe']('wlan0', 'LabWifi', 'private123',
                                         root / 'net', profiles, run)
            self.assertEqual(observed['status'], 'pass')
            self.assertNotIn('private123', repr(commands))
            self.assertNotIn('private123', repr(observed))
            profile = next(profiles.iterdir())
            self.assertEqual(stat.S_IMODE(profile.stat().st_mode), 0o600)

    def test_proxy_rejects_embedded_credentials(self):
        observed = PROXY['probe']('http', 'http://user:password@proxy.example:8080')
        self.assertEqual(observed['status'], 'fail')
        self.assertNotIn('password', repr(observed))

    def test_proxy_clear_removes_legacy_setting(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old_shell = root / 'proxy.sh'
            old_apt = root / '01proxy'
            old_shell.write_text('export http_proxy="http://old:8080"\nexport ftp_proxy="http://ftp:21"\n')
            old_apt.write_text('Acquire::http::Proxy "http://old:8080";\n')
            with patch.object(PROXY['os'], 'geteuid', return_value=0):
                observed = PROXY['probe']('http', '', root / 'new.sh', root / 'newapt',
                                          old_shell, old_apt)
            self.assertEqual(observed['status'], 'pass')
            self.assertNotIn('http_proxy', old_shell.read_text())
            self.assertIn('ftp_proxy', old_shell.read_text())
            self.assertNotIn('http::Proxy', old_apt.read_text())

    def test_journal_default_removes_legacy_dropin(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            old = root / '80-robopi-config-journal-storage.conf'
            old.write_text('# Created/managed by robopi-config\n[Journal]\nStorage=persistent\n')
            run = lambda args, **kw: subprocess.CompletedProcess(args, 0, '', '')
            with patch.object(JOURNAL['os'], 'geteuid', return_value=0):
                observed = JOURNAL['probe']('default', root / 'new.conf', run, old)
            self.assertEqual(observed['status'], 'pass')
            self.assertFalse(old.exists())

    def test_labwc_blanking_updates_only_managed_line(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            autostart = root / '.config/labwc/autostart'
            autostart.parent.mkdir(parents=True)
            autostart.write_text('waybar &\n')
            account = SimpleNamespace(pw_dir=str(root), pw_uid=1000, pw_gid=1000)
            with patch.object(BLANKING['os'], 'geteuid', return_value=0), \
                 patch.object(BLANKING['os'], 'chown'), \
                 patch.object(BLANKING['pwd'], 'getpwnam', return_value=account):
                enabled = BLANKING['probe']('labwc', 'enable', 'robo', greeter=root / 'missing/autostart')
                disabled = BLANKING['probe']('labwc', 'disable', 'robo', greeter=root / 'missing/autostart')
            self.assertEqual(enabled['status'], 'needs_review')
            self.assertEqual(disabled['status'], 'needs_review')
            self.assertEqual(autostart.read_text(), 'waybar &\n')

    def test_x11_blanking_uses_embedded_config(self):
        with tempfile.TemporaryDirectory() as temp:
            setting = Path(temp) / 'xorg.conf.d/10-blanking.conf'
            with patch.object(BLANKING['os'], 'geteuid', return_value=0):
                disabled = BLANKING['probe']('x11', 'disable', setting=setting)
                self.assertEqual(disabled['status'], 'needs_review')
                self.assertEqual(setting.read_text(), BLANKING['X11_BLANKING_DISABLED'])
                self.assertIn('Option      "DPMS" "Disable"', setting.read_text())
                enabled = BLANKING['probe']('x11', 'enable', setting=setting)
            self.assertEqual(enabled['status'], 'needs_review')
            self.assertFalse(setting.exists())


if __name__ == '__main__':
    unittest.main()
