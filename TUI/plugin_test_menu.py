# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Render plugin test menus, prompts and reports in the TUI."""

import json
import os
from pathlib import Path
import re
import socket
import subprocess


SOURCE_EXECUTOR = Path(__file__).resolve().parent.parent / 'loader' / 'plugin_executor.py'
EXECUTOR = (SOURCE_EXECUTOR if SOURCE_EXECUTOR.is_file() else
            Path(__file__).with_name('loader') / 'plugin_executor.py')


def command(args, timeout=10, input_data=None):
    try:
        completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout,
                                   input=input_data,
                                   check=False)
        return completed.returncode, completed.stdout.strip(), completed.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 1, '', str(exc)


def load_catalog(runner=EXECUTOR, save=None, develop=False):
    if save is None:
        save = os.geteuid() == 0
    rc, payload, error = command(['python3', str(runner), '--env', 'tui',
                                  '--client-id', socket.gethostname(), '--list',
                                  *(['--include-all'] if develop else []),
                                  *([] if save else ['--no-save'])])
    if rc:
        raise ValueError(error or 'Could not list plugins')
    try:
        return json.loads(payload)['tests']
    except (ValueError, KeyError, TypeError) as exc:
        raise ValueError('Invalid plugin catalog') from exc


def plugin_tests_menu(ui, runner=EXECUTOR, selected=None, category=None, develop=False):
    if not runner.is_file():
        ui.message('Tests', f'Test runner not installed: {runner}')
        return
    while True:
        try:
            tests = load_catalog(runner, develop=develop)
        except ValueError as exc:
            ui.message('Tests', str(exc))
            return
        if category:
            tests = [test for test in tests if test.get('category', '板端测试') == category]
        if not develop:
            tests = [test for test in tests if test['lifecycle'] == 'official']
        if not tests:
            ui.message('Tests', 'No tests installed.')
            return
        items = ([('all', 'Run eligible batch checks')] if not category else [])
        items.extend((test['id'], f"[{test.get('category', 'Board')}] "
                      f"{test['name']} v{test['version']} [{test['lifecycle']}]"
                      + ('' if 'tui' in test['clients'] else ' [csharp only]')
                      + ('' if test['available'] else ' [unavailable]')) for test in tests)
        choice = selected or ui.menu(category or 'Board plugins', items)
        if choice is None:
            return
        chosen = next((test for test in tests if test['id'] == choice), None)
        if selected and not chosen:
            ui.message('Tests', f'Test {selected} is not installed.')
            return
        if chosen and 'tui' not in chosen['clients']:
            ui.message('Tests', f'Test {choice} is only available to another client.')
            if selected:
                return
            continue
        if chosen and chosen['lifecycle'] == 'deprecated':
            ui.message('Tests', f'Test {choice} is deprecated and cannot run.')
            if selected:
                return
            continue
        if chosen and chosen.get('safety') == 'active' and os.geteuid() != 0:
            ui.message('Permission required', 'Run sudo robopi-tui for active plugins.')
            if selected:
                return
            continue
        extra = []
        if chosen and chosen.get('inputs'):
            params = {}
            cancelled = False
            for field in chosen['inputs']:
                if any(params.get(key) != expected
                       for key, expected in field.get('when', {}).items()):
                    continue
                label = field['label']
                if field['type'] == 'choice':
                    value = ui.menu(label, [(item, item) for item in field['choices']])
                elif field['type'] == 'boolean':
                    value = ui.yes(label, label)
                elif field['type'] == 'secret':
                    value = ui.dialog('--title', label, '--passwordbox', label, '11', '76',
                                      capture=True)
                else:
                    default = str(field.get('default', ''))
                    value = ui.input(label, label, default)
                if value is None:
                    cancelled = True
                    break
                if value == '' and field.get('required'):
                    ui.message(label, 'A value is required.')
                    cancelled = True
                    break
                if value == '' and not field.get('required'):
                    continue
                if field['type'] == 'integer':
                    try:
                        value = int(value)
                    except ValueError:
                        ui.message(label, 'Enter an integer.')
                        cancelled = True
                        break
                    if value < field.get('minimum', value) or value > field.get('maximum', value):
                        ui.message(label, 'Value is outside the allowed range.')
                        cancelled = True
                        break
                elif field['type'] in ('text', 'secret') and field.get('pattern'):
                    if not re.fullmatch(field['pattern'], value):
                        ui.message(label, 'Value has an invalid format.')
                        cancelled = True
                        break
                params[field['name']] = value
            if cancelled:
                if selected:
                    return
                continue
            secret = any(field['type'] == 'secret' for field in chosen['inputs'])
            extra = ['--params-stdin'] if secret else [
                '--params', json.dumps(params, ensure_ascii=False)]
            input_data = json.dumps(params, ensure_ascii=False) if secret else None
        else:
            input_data = None
        if chosen and chosen.get('safety') == 'active':
            warning = chosen.get('confirm') or f"Run {chosen['name']} on this board?"
            if not ui.yes('Active board test', warning):
                if selected:
                    return
                continue
        rc, payload, error = command(['python3', str(runner), '--env', 'tui',
                                      '--client-id', socket.gethostname(), '--run', choice,
                                      *extra], timeout=None, input_data=input_data)
        if rc:
            ui.message('Tests', error or 'Test run failed.')
            if selected:
                return
            continue
        try:
            report = json.loads(payload)
            rows = [f"Run: {report['run_id']}", f"Outcome: {report['outcome']}", '']
            if error.startswith('Saved report: '):
                rows.insert(2, error)
            for item in report['results']:
                value = (f"{item['value']} {item['unit'] or ''}"
                         if item['value'] is not None else '')
                station = ', '.join(item['station'])
                rows.append(f"[{item['id']}] {item['name']} ({station}): "
                            f"{item['result']} {value}".strip())
                if item.get('author'):
                    rows.append(f"  Author: {item['author']}")
                rows.append(f"  Plugin version: {item['plugin_version']}")
                rows.append(f"  Lifecycle: {item['lifecycle']}")
                if item.get('plugin'):
                    rows.append('  Plugin fields:')
                    rows.append(json.dumps(item['plugin'], ensure_ascii=False, indent=2))
                if item.get('parameters'):
                    rows.append('  Parameters: '
                                + json.dumps(item['parameters'], ensure_ascii=False))
                if item.get('exit_code') is not None:
                    rows.append(f"  Exit code: {item['exit_code']}")
                if item.get('started_at') and item.get('finished_at'):
                    rows.append(f"  {item['started_at']} -> {item['finished_at']}")
                rows.append(f"  {item['message']}")
                if item.get('details'):
                    rows.append(json.dumps(item['details'], ensure_ascii=False, indent=2))
                for log in item.get('logs', []):
                    rows.append(f"  [{log['timestamp']}] {log['source']}: {log['message']}")
                rows.append('')
            ui.output('Test results', '\n'.join(rows))
        except (ValueError, KeyError, TypeError):
            ui.message('Tests', 'Invalid test report.')
        if selected:
            return
