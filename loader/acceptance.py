# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 RoboParty

"""Per-device acceptance records keyed by hardware serial (machine ID fallback).

Records are small index files next to the full job/plugin reports:
  <root>/<sn-...|machine-...>/<timestamp>_<id>.json
"""

from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import re
import tempfile

SCHEMA_VERSION = 1
DEFAULT_ROOT = Path('/var/lib/robopi-tui/acceptance')


def _safe(value, fallback: str) -> str:
    text = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(value or '')).strip('._-')
    return (text or fallback)[:128]


def identity_key(identity: dict | None) -> str:
    identity = identity or {}
    serial = str(identity.get('serial') or '').strip()
    if serial:
        return 'sn-' + _safe(serial, 'unknown')
    return 'machine-' + _safe(identity.get('machineId'), 'unknown')


def _atomic_write(path: Path, data: dict):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if path.parent.is_symlink() or path.parent.stat().st_mode & 0o077:
        raise OSError('acceptance directory must be private')
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.record-', delete=False) as stream:
            name = stream.name
            json.dump(data, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def write(root, kind: str, identifier: str, identity: dict | None, payload: dict,
          timestamp: str | None = None):
    stamp = timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat()
    directory = Path(root) / identity_key(identity)
    compact = _safe(stamp.replace(':', '').replace('-', '').replace('+', '_'), 'time')
    target = directory / (compact + '_' + _safe(identifier, 'record') + '.json')
    record = {
        'schemaVersion': SCHEMA_VERSION,
        'kind': kind,
        'identity': identity or {},
        'timestamp': stamp,
        'payload': payload,
    }
    _atomic_write(target, record)
    return target
