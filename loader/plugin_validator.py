#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Validate plugin metadata and entrypoints without executing plugin code."""

import argparse
import ast
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from loader.plugin_catalog import PLUGIN_DIR, PLUGIN_FIELDS, load_plugins


def _main_guard(test):
    if not isinstance(test, ast.Compare) or len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    if len(test.comparators) != 1:
        return False
    sides = (test.left, test.comparators[0])
    return (any(isinstance(side, ast.Name) and side.id == '__name__' for side in sides)
            and any(isinstance(side, ast.Constant) and side.value == '__main__'
                    for side in sides))


def check_plugins(directory=PLUGIN_DIR):
    directory = Path(directory)
    plugins = load_plugins(directory)
    if not plugins:
        raise ValueError(f'No plugins found: {directory}')
    for plugin in plugins:
        script = directory / plugin['_script']
        module = ast.parse(script.read_text(encoding='utf-8'), filename=str(script))
        definition = next(node.value for node in module.body
                          if isinstance(node, ast.Assign)
                          and any(isinstance(target, ast.Name) and target.id == 'PLUGIN'
                                  for target in node.targets))
        metadata = ast.literal_eval(definition)
        unknown = set(metadata) - set(PLUGIN_FIELDS)
        if unknown:
            raise ValueError(f'{script.name}: unknown PLUGIN fields: '
                             f'{", ".join(sorted(map(str, unknown)))}')
        if not any(isinstance(node, ast.If) and _main_guard(node.test) for node in module.body):
            raise ValueError(f'{script.name}: missing if __name__ == "__main__" entrypoint')
    return plugins


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=PLUGIN_DIR,
                        help='plugin directory to inspect (default: installed plugins)')
    args = parser.parse_args(argv)
    try:
        plugins = check_plugins(args.directory)
    except (OSError, ValueError, SyntaxError) as exc:
        print(f'plugin-check: {exc}', file=sys.stderr)
        return 1
    print(f'Checked {len(plugins)} plugin(s): {args.directory}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
