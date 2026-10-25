# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Discover and validate literal plugin metadata for the client catalog."""

import ast
import os
from pathlib import Path
import re
import shutil


SCHEMA_VERSION = 3
PLUGIN_DIR = Path(__file__).resolve().parent.parent / 'plugins'
LIFECYCLES = ('official', 'testing', 'deprecated')
CLIENTS = ('tui', 'csharp')
INPUT_TYPES = ('text', 'choice', 'integer', 'boolean', 'secret')
ID_PATTERN = re.compile(r'RP[0-9]{3}\Z')
PLUGIN_FILENAME = re.compile(r'([0-9]{3})-[a-z][a-z0-9_]*\.py\Z')
PLUGIN_FIELDS = (
    'id', 'station', 'clients', 'author', 'name', 'documentation', 'version', 'lifecycle', 'kind',
    'category', 'batch', 'confirm', 'inputs', 'safety', 'requires',
    'depends_on', 'timeout_s',
)


def has_capability(name):
    if name == 'thermal':
        return any(Path('/sys/class/thermal').glob('thermal_zone*/temp'))
    if name == 'network':
        root = Path('/sys/class/net')
        return root.is_dir() and any(path.name != 'lo' for path in root.iterdir())
    if name == 'usb':
        return any(Path('/sys/bus/usb/devices').glob('*/idVendor'))
    if name == 'can':
        return any(re.fullmatch(r'can[0-9]+', path.name)
                   for path in Path('/sys/class/net').glob('can[0-9]*'))
    if name == 'udc':
        return any(Path('/sys/class/udc').glob('*/state'))
    if name == 'drm':
        return any(Path('/sys/class/drm').glob('card*-*/status'))
    if name == 'gpio':
        return os.access('/sys/kernel/debug/gpio', os.R_OK) or shutil.which('gpioinfo') is not None
    if name == 'serial':
        return any(re.fullmatch(r'tty(?:S|AMA|USB|ACM)[0-9]+', path.name)
                   for pattern in ('ttyS[0-9]*', 'ttyAMA[0-9]*', 'ttyUSB[0-9]*',
                                   'ttyACM[0-9]*') for path in Path('/dev').glob(pattern))
    if name == 'apt':
        return shutil.which('apt-get') is not None
    return False


def load_plugins(directory=PLUGIN_DIR, overrides=None):
    plugins = []
    overrides = overrides or {}
    for script in sorted(directory.glob('*.py')):
        filename = PLUGIN_FILENAME.fullmatch(script.name)
        if filename is None:
            raise ValueError(f'Invalid plugin filename: {script.name}')
        if script.is_symlink():
            raise ValueError(f'Symlinked plugin script is not allowed: {script}')
        try:
            source = overrides.get(script.name)
            if source is None:
                source = script.read_text(encoding='utf-8')
            module = ast.parse(source, filename=str(script))
            definitions = [node.value for node in module.body
                           if isinstance(node, ast.Assign)
                           and any(isinstance(target, ast.Name) and target.id == 'PLUGIN'
                                   for target in node.targets)]
            if len(definitions) != 1:
                raise ValueError('Expected exactly one literal PLUGIN definition')
            metadata = ast.literal_eval(definitions[0])
        except (OSError, SyntaxError, ValueError, TypeError) as exc:
            raise ValueError(f'Invalid plugin metadata {script.name}: {exc}') from exc
        if not isinstance(metadata, dict):
            raise ValueError(f'Plugin metadata must be a dict: {script.name}')
        plugin_id = metadata.get('id')
        if not isinstance(plugin_id, str) or not ID_PATTERN.fullmatch(plugin_id):
            raise ValueError(f'Invalid plugin id in {script.name}')
        if plugin_id != 'RP' + filename.group(1):
            raise ValueError(f'Plugin filename number must match id: {script.name}')
        station = metadata.get('station')
        if (not isinstance(station, list) or not station
                or any(not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', name)
                       for name in station) or len(station) != len(set(station))):
            raise ValueError(f'Invalid board station list: {plugin_id}')
        clients = metadata.get('clients')
        if (not isinstance(clients, list) or not clients
                or any(client not in CLIENTS for client in clients)
                or len(clients) != len(set(clients))):
            raise ValueError(f'Invalid plugin clients: {plugin_id}')
        if not isinstance(metadata.get('author'), str) or not metadata['author'].strip():
            raise ValueError(f'Missing test author: {plugin_id}')
        if not isinstance(metadata.get('name'), str) or not metadata['name'].strip():
            raise ValueError(f'Missing plugin name: {plugin_id}')
        documentation = metadata.get('documentation')
        if (not isinstance(documentation, dict)
                or set(documentation) != {'title', 'criterion'}
                or any(not isinstance(documentation[key], str) or not documentation[key].strip()
                       for key in ('title', 'criterion'))):
            raise ValueError(f'Invalid plugin documentation: {plugin_id}')
        if not isinstance(metadata.get('version'), str) or not metadata['version'].strip():
            raise ValueError(f'Missing plugin version: {plugin_id}')
        if metadata.get('lifecycle') not in LIFECYCLES:
            raise ValueError(f'Invalid plugin lifecycle: {plugin_id}')
        kind = metadata.get('kind', 'test')
        if kind not in ('test', 'action'):
            raise ValueError(f'Invalid plugin kind: {plugin_id}')
        category = metadata.get('category', '板端测试')
        if not isinstance(category, str) or not category.strip():
            raise ValueError(f'Invalid plugin category: {plugin_id}')
        batch = metadata.get('batch', kind == 'test')
        if type(batch) is not bool:
            raise ValueError(f'Invalid plugin batch flag: {plugin_id}')
        confirm = metadata.get('confirm', '')
        if not isinstance(confirm, str):
            raise ValueError(f'Invalid plugin confirmation: {plugin_id}')
        inputs = metadata.get('inputs', [])
        if not isinstance(inputs, list):
            raise ValueError(f'Invalid plugin inputs: {plugin_id}')
        names = set()
        for field in inputs:
            if not isinstance(field, dict) or set(field) - {
                    'name', 'label', 'type', 'choices', 'required', 'default', 'pattern',
                    'minimum', 'maximum', 'when'}:
                raise ValueError(f'Invalid input field: {plugin_id}')
            name = field.get('name')
            if (not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', name)
                    or name in names or not isinstance(field.get('label'), str)
                    or not field['label'].strip() or field.get('type') not in INPUT_TYPES):
                raise ValueError(f'Invalid input field: {plugin_id}')
            names.add(name)
            if 'required' in field and type(field['required']) is not bool:
                raise ValueError(f'Invalid input requirement: {plugin_id}')
            if 'choices' in field and (field['type'] != 'choice'
                    or not isinstance(field['choices'], list) or not field['choices']
                    or any(not isinstance(item, str) for item in field['choices'])):
                raise ValueError(f'Invalid input choices: {plugin_id}')
            if field['type'] == 'choice' and 'choices' not in field:
                raise ValueError(f'Missing input choices: {plugin_id}')
            if 'pattern' in field and (field['type'] not in ('text', 'secret')
                    or not isinstance(field['pattern'], str)):
                raise ValueError(f'Invalid input pattern: {plugin_id}')
            if 'pattern' in field:
                try:
                    re.compile(field['pattern'])
                except re.error as exc:
                    raise ValueError(f'Invalid input pattern: {plugin_id}') from exc
            if any(key in field for key in ('minimum', 'maximum')) and field['type'] != 'integer':
                raise ValueError(f'Invalid input bounds: {plugin_id}')
            if any(type(field[key]) is not int for key in ('minimum', 'maximum') if key in field):
                raise ValueError(f'Invalid input bounds: {plugin_id}')
            if field.get('minimum', 0) > field.get('maximum', float('inf')):
                raise ValueError(f'Reversed input bounds: {plugin_id}')
            if 'when' in field and (not isinstance(field['when'], dict)
                    or any(not isinstance(k, str) or not isinstance(v, (str, bool, int))
                           for k, v in field['when'].items())):
                raise ValueError(f'Invalid input condition: {plugin_id}')
            if 'default' in field:
                default = field['default']
                if (field['type'] == 'integer' and type(default) is not int
                        or field['type'] == 'boolean' and type(default) is not bool
                        or field['type'] in ('text', 'choice', 'secret') and not isinstance(default, str)):
                    raise ValueError(f'Invalid input default: {plugin_id}')
                if field['type'] == 'choice' and default not in field['choices']:
                    raise ValueError(f'Invalid input default: {plugin_id}')
                if field['type'] == 'integer' and (default < field.get('minimum', default)
                        or default > field.get('maximum', default)):
                    raise ValueError(f'Invalid input default: {plugin_id}')
        safety = metadata.get('safety')
        if safety not in ('passive', 'query', 'active'):
            raise ValueError(f'Invalid plugin safety level: {plugin_id}')
        if (kind == 'action' or safety == 'active') and clients != ['tui']:
            raise ValueError(f'Active or configuration plugin must be TUI-only: {plugin_id}')
        requires = metadata.get('requires', [])
        if not isinstance(requires, list) or any(not isinstance(x, str) for x in requires):
            raise ValueError(f'Invalid capability list: {plugin_id}')
        depends_on = metadata.get('depends_on', [])
        if (not isinstance(depends_on, list) or any(not isinstance(x, str)
                                                   or not ID_PATTERN.fullmatch(x)
                                                   for x in depends_on)
                or len(depends_on) != len(set(depends_on))):
            raise ValueError(f'Invalid dependency list: {plugin_id}')
        timeout = metadata.get('timeout_s', 10)
        maximum = 3600 if safety == 'active' else 30
        if type(timeout) is not int or not 1 <= timeout <= maximum:
            raise ValueError(f'Plugin timeout must be 1..{maximum} seconds: {plugin_id}')
        plugins.append({**metadata, 'requires': requires, 'depends_on': depends_on,
                        'timeout_s': timeout, 'kind': kind, 'category': category,
                        'batch': batch, 'confirm': confirm, 'inputs': inputs,
                        '_script': script.name})
    execution_order(plugins)
    by_id = {plugin['id']: plugin for plugin in plugins}
    for plugin in plugins:
        for dependency in plugin['depends_on']:
            if not set(plugin['clients']).issubset(by_id[dependency]['clients']):
                raise ValueError(f'Dependency {dependency} does not support every client of {plugin["id"]}')
    return plugins


def execution_order(plugins, selected='all'):
    by_id = {plugin['id']: plugin for plugin in plugins}
    if len(by_id) != len(plugins):
        raise ValueError('Duplicate plugin IDs')
    if selected != 'all' and selected not in by_id:
        raise ValueError(f'Unknown test: {selected}')
    ordered = []
    state = {}

    def visit(plugin):
        plugin_id = plugin['id']
        if state.get(plugin_id) == 'visiting':
            raise ValueError(f'Plugin dependency cycle at {plugin_id}')
        if state.get(plugin_id) == 'done':
            return
        state[plugin_id] = 'visiting'
        for dependency in plugin['depends_on']:
            if dependency not in by_id:
                raise ValueError(f'Missing dependency {dependency} for {plugin_id}')
            visit(by_id[dependency])
        state[plugin_id] = 'done'
        ordered.append(plugin)

    for plugin in plugins if selected == 'all' else [by_id[selected]]:
        visit(plugin)
    return ordered


def available(plugin, checker=has_capability):
    missing = [name for name in plugin['requires'] if not checker(name)]
    return not missing, missing


def catalog(plugins, checker=has_capability, client=None, include_all=False):
    tests = []
    for plugin in execution_order(plugins):
        if client and client not in plugin['clients'] and not include_all:
            continue
        runnable, missing = available(plugin, checker)
        tests.append({'id': plugin['id'], 'name': plugin['name'],
                      'documentation': plugin['documentation'],
                      'station': plugin['station'], 'clients': plugin['clients'],
                      'author': plugin['author'],
                      'version': plugin['version'], 'safety': plugin['safety'],
                      'lifecycle': plugin['lifecycle'],
                      'kind': plugin.get('kind', 'test'),
                      'category': plugin.get('category', '板端测试'),
                      'batch': plugin.get('batch', True),
                      'confirm': plugin.get('confirm', ''),
                      'inputs': plugin.get('inputs', []),
                      'depends_on': plugin['depends_on'],
                      'available': (runnable and plugin['lifecycle'] != 'deprecated'
                                    and (client is None or client in plugin['clients'])),
                      'missing_capabilities': missing})
    return {
        'schema_version': SCHEMA_VERSION,
        'tests': tests,
    }
