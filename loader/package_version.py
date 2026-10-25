# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty

"""Read the TUI package version from its Debian changelog."""

import gzip
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parent.parent


def package_version(root=ROOT):
    for changelog in (root / 'debian' / 'changelog',
                      root.parents[1] / 'share' / 'doc' / 'robopi-tui' / 'changelog.gz'):
        if not changelog.is_file():
            continue
        opener = gzip.open if changelog.suffix == '.gz' else open
        with opener(changelog, 'rt', encoding='utf-8') as source:
            header = source.readline()
        match = re.match(r'^robopi-tui \(([^)]+)\) ', header)
        if not match:
            raise ValueError(f'Invalid Debian changelog header: {changelog}')
        return match.group(1)
    raise FileNotFoundError('RoboPi TUI Debian changelog is missing')
