# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Read and safely update literal plugin metadata without executing plugins."""

import ast
import json
import os
import pprint

from loader.plugin_catalog import LIFECYCLES, PLUGIN_DIR, PLUGIN_FIELDS, load_plugins
from loader.plugin_helpers import atomic_write


EDITABLE_FIELDS = PLUGIN_FIELDS[1:]


def _definition(source, filename):
    module = ast.parse(source, filename=filename)
    definitions = [node.value for node in module.body
                   if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == 'PLUGIN'
                           for target in node.targets)]
    if len(definitions) != 1 or not isinstance(definitions[0], ast.Dict):
        raise ValueError('Expected exactly one literal PLUGIN dictionary')
    return definitions[0]


def _offset(lines, lineno, column):
    return sum(len(line) for line in lines[:lineno - 1]) + column


def _render(value, column):
    formatted = pprint.pformat(value, width=max(40, 88 - column), sort_dicts=False)
    return formatted.replace('\n', '\n' + ' ' * column).encode('utf-8')


def replace_field(source, filename, field, value):
    if field not in EDITABLE_FIELDS:
        raise ValueError(f'Field cannot be edited: {field}')
    data = source.encode('utf-8')
    lines = data.splitlines(keepends=True)
    definition = _definition(source, filename)
    for key, node in zip(definition.keys, definition.values):
        if isinstance(key, ast.Constant) and key.value == field:
            start = _offset(lines, node.lineno, node.col_offset)
            end = _offset(lines, node.end_lineno, node.end_col_offset)
            rendered = _render(value, node.col_offset)
            return (data[:start] + rendered + data[end:]).decode('utf-8')

    close = _offset(lines, definition.end_lineno, definition.end_col_offset) - 1
    line_start = data.rfind(b'\n', 0, close) + 1
    key_prefix = repr(field).encode('ascii') + b': '
    if not data[line_start:close].strip():
        previous = data[:line_start].rstrip()
        comma = b'' if previous.endswith((b'{', b',')) else b','
        key_value = key_prefix + _render(value, 4 + len(key_prefix))
        return (data[:line_start].rstrip(b'\n') + comma + b'\n'
                + b'    ' + key_value + b',\n' + data[line_start:]).decode('utf-8')
    prefix = b'' if data[:close].rstrip().endswith((b'{', b',')) else b', '
    key_value = key_prefix + _render(value, close - line_start + len(prefix) + len(key_prefix))
    return (data[:close] + prefix + key_value + data[close:]).decode('utf-8')


def plugin_metadata(plugin):
    return {key: value for key, value in plugin.items() if key != '_script'}


def set_field(plugin_id, field, value, directory=PLUGIN_DIR):
    if os.geteuid() != 0:
        raise PermissionError('Run sudo robopi-tui to change plugin metadata')
    plugins = load_plugins(directory)
    plugin = next((item for item in plugins if item['id'] == plugin_id), None)
    if plugin is None:
        raise ValueError(f'Unknown plugin: {plugin_id}')
    script = directory / plugin['_script']
    source = script.read_text(encoding='utf-8')
    candidate = replace_field(source, script.name, field, value)
    load_plugins(directory, overrides={script.name: candidate})
    if script.read_text(encoding='utf-8') != source:
        raise RuntimeError(f'Plugin changed while editing: {script.name}')
    atomic_write(script, candidate)


def _json(value):
    return json.dumps(value, ensure_ascii=False, indent=2)


def _reject_json_constant(token):
    raise ValueError(f'Invalid JSON value: {token}')


def manage_plugins(ui, directory=PLUGIN_DIR):
    while True:
        try:
            plugins = load_plugins(directory)
        except ValueError as exc:
            ui.message('Plugin metadata', str(exc))
            return
        choice = ui.menu('Plugin metadata', [
            (item['id'], f"{item['name']} v{item['version']} [{item['lifecycle']}]")
            for item in plugins
        ], 'Select a plugin to inspect or edit')
        if choice is None:
            return
        plugin = next(item for item in plugins if item['id'] == choice)
        while True:
            action = ui.menu(f"{choice} {plugin['name']}", [
                ('show', 'View all metadata as JSON'),
                ('lifecycle', 'Change lifecycle'),
                ('field', 'Edit a metadata field'),
            ])
            if action is None:
                break
            if action == 'show':
                ui.output(choice, _json(plugin_metadata(plugin)))
                continue
            if os.geteuid() != 0:
                ui.message('Permission required', 'Run sudo robopi-tui to edit plugins.')
                continue
            if action == 'lifecycle':
                field = 'lifecycle'
                value = ui.menu('Lifecycle', [(state, state) for state in LIFECYCLES],
                                f"Current: {plugin['lifecycle']}")
                if value is None:
                    continue
            else:
                field = ui.menu('Metadata field', [
                    (key, _json(plugin.get(key))[:60].replace('\n', ' '))
                    for key in EDITABLE_FIELDS
                ])
                if field is None:
                    continue
                raw = ui.edit(f'{choice} {field} (JSON)', _json(plugin.get(field)))
                if raw is None:
                    continue
                try:
                    value = json.loads(raw, parse_constant=_reject_json_constant)
                except ValueError as exc:
                    ui.message('Invalid JSON', str(exc))
                    continue
            if value == plugin.get(field):
                continue
            prompt = (f"Change {choice} lifecycle: {plugin['lifecycle']} -> {value}?"
                      if field == 'lifecycle' else f'Save {choice}.{field}?')
            if not ui.yes('Confirm metadata change', prompt):
                continue
            try:
                set_field(choice, field, value, directory)
                plugin = next(item for item in load_plugins(directory) if item['id'] == choice)
                ui.message('Plugin updated', f'{choice}.{field} updated.')
            except (OSError, ValueError, RuntimeError) as exc:
                ui.message('Update rejected', str(exc))


