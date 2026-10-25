#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Generate the plugin status document from each plugin's literal metadata."""

import argparse
from collections import Counter
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from loader.plugin_catalog import PLUGIN_DIR, load_plugins
from loader.plugin_helpers import atomic_write


STATUS = PLUGIN_DIR / 'STATUS.md'


def render_status(plugins):
    stations = {tuple(plugin['station']) for plugin in plugins}
    authors = {plugin['author'] for plugin in plugins}
    lines = [
        '# 插件状态清单',
        '',
        '此表由 `python3 loader/generate_plugin_status.py --write` 从各插件的 `PLUGIN` 元数据生成。'
        '字段及编写规则见 [README.md](README.md)。',
        '',
        f'当前 **{len(plugins)} 项**；生命周期：' + '、'.join(
            f'`{name}` {count} 项' for name, count in sorted(
                Counter(plugin['lifecycle'] for plugin in plugins).items())) + '。',
    ]
    if len(stations) == 1 and len(authors) == 1:
        lines.append('全部插件声明适用板卡：`' + '`, `'.join(next(iter(stations)))
                     + '`；编写人：`' + next(iter(authors))
                     + '`。板卡声明不等于实机验收。')
    else:
        lines.append('各插件的板卡与编写人以各自 `PLUGIN` 字段为准。')
    lines += [
        '',
        '`批量=是` 只表示 `batch=True`；`active` 项在 `--run all` 中仍会跳过，必须指定编号。'
        '`TUI+C#` 表示两个客户端均可调用。',
        '',
        '| 编号 | 版本 | 分类 | 项目 | 生命周期 | 类型 / 安全 | 客户端 | 批量 | 前置 | 判据 / 结果边界 |',
        '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |',
    ]
    for plugin in sorted(plugins, key=lambda item: item['id']):
        clients = '+'.join('TUI' if client == 'tui' else 'C#'
                           for client in plugin['clients'])
        values = (plugin['id'], plugin['version'], plugin['category'],
                  plugin['documentation']['title'],
                  plugin['lifecycle'], f"{plugin['kind']} / {plugin['safety']}", clients,
                  '是' if plugin['batch'] else '否',
                  ', '.join(plugin['depends_on']) or '无',
                  plugin['documentation']['criterion'])
        lines.append('| ' + ' | '.join(str(value).replace('|', '\\|') for value in values) + ' |')
    lines += [
        '',
        '生命周期描述的是插件验收状态，不是单次运行结果。`testing` 不会因一次 `pass` 自动变成 '
        '`official`；`deprecated` 可列出但不能执行。需要人工判断的项目返回 `needs_review`，'
        '不等于通过。现有项目尚未完成所有声明板卡的实机验收。',
        '',
    ]
    return '\n'.join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group()
    actions.add_argument('--check', action='store_true', help='fail if the status document is stale')
    actions.add_argument('--write', action='store_true', help='update the status document')
    parser.add_argument('--plugins', type=Path, default=PLUGIN_DIR)
    parser.add_argument('--output', type=Path, default=STATUS)
    args = parser.parse_args(argv)
    try:
        content = render_status(load_plugins(args.plugins))
        if args.check:
            if args.output.read_text(encoding='utf-8') != content:
                raise ValueError(f'Stale status document: {args.output}')
            print(f'Current status document: {args.output}')
        elif args.write:
            atomic_write(args.output, content)
            print(f'Updated status document: {args.output}')
        else:
            print(content, end='')
    except (OSError, ValueError) as exc:
        print(f'plugin-status: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
