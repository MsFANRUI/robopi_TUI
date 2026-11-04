# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 RoboParty

"""Read-only motor error/state snapshot via motors_py.

Safety contract:
  * Only ``MotorDriver.create_motor`` and getters are used.
  * ``init_motor`` / ``lock_motor`` / ``refresh_motor_status`` /
    ``clear_motor_error`` are never called — they enable, command or reset.
  * No CAN frame is transmitted. A separate raw SocketCAN socket only counts
    feedback frames to tell "no feedback" from "feedback says no error".
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path
import socket
import struct
import sys
import time
from typing import Callable, Optional

import yaml

SETTLE_SECONDS = 0.8
CAN_EFF_MASK = 0x1FFFFFFF

ERROR_NAMES = {
    "DM": {
        0x00: "DM_DOWN", 0x01: "DM_UP", 0x08: "DM_OVER_VOLT", 0x09: "DM_UNDER_VOLT",
        0x0A: "DM_OVER_CURRENT", 0x0B: "DM_MOS_OVER_TEMP", 0x0C: "DM_COIL_OVER_TEMP",
        0x0D: "DM_LOST_CONN", 0x0E: "DM_OVER_LOAD",
    },
    "LRO": {
        0x00: "LRO_NO_ERROR", 0x01: "LRO_MOTOR_OVERHEAT", 0x02: "LRO_OVER_CURRENT",
        0x03: "LRO_UNDER_VOLTAGE", 0x04: "LRO_ENCODER_ERROR", 0x06: "LRO_BRAKE_OVERVOLT",
        0x07: "LRO_DRV_ERROR",
    },
    "EVO": {
        0x00: "EVO_NO_ERROR", 0x01: "EVO_OVER_VOLTAGE", 0x02: "EVO_UNDER_VOLTAGE",
        0x03: "EVO_ELECTRIC_ANGLE_ERROR", 0x04: "EVO_DRV_ERROR",
        0x05: "EVO_BUS_OVER_CURRENT", 0x06: "EVO_PHASE_A_OVER_CURRENT",
        0x07: "EVO_PHASE_B_OVER_CURRENT", 0x08: "EVO_PHASE_C_OVER_CURRENT",
        0x09: "EVO_PCB_OVER_TEMP", 0x0A: "EVO_COIL_OVER_TEMP", 0x0B: "EVO_ENCODER_ERROR",
        0x0C: "EVO_CURRENT_SENSOR_ERROR", 0x0D: "EVO_POSITION_OVER_LIMIT",
        0x0E: "EVO_OVER_SPEED", 0x0F: "EVO_STALL_PROTECTION", 0x10: "EVO_CAN_COMM_LOST",
    },
    "XYN": {
        0x00: "XYN_NO_ERROR", 0x01: "XYN_OVER_VOLTAGE", 0x02: "XYN_OVER_CURRENT",
        0x03: "XYN_MOTOR_OVER_TEMP", 0x04: "XYN_BOARD_OVER_TEMP", 0x05: "XYN_UNDER_VOLTAGE",
        0x06: "XYN_ENCODER_FAULT", 0x07: "XYN_COMM_FAULT", 0x08: "XYN_WARN_MOTOR_OVER_TEMP",
        0x09: "XYN_WARN_BOARD_OVER_TEMP",
    },
}


def error_name(motor_type: str, code: int) -> str:
    if code == 0:
        return f"{motor_type}_NO_ERROR"
    return ERROR_NAMES.get(motor_type, {}).get(code, f"{motor_type}_ERROR_0x{code:02X}")


def config_path(explicit: Optional[str] = None) -> Path:
    candidates = [explicit, os.environ.get("RP_ROBOT_CONFIG", "")]
    candidates += [
        "/opt/roboparty/share/roboparty_inference/robots/rpo/robot.yaml",
        "/opt/roboparty/share/roboparty_inference/robots/rp1/robot.yaml",
    ]
    for value in candidates:
        if value and Path(value).is_file():
            return Path(value)
    raise FileNotFoundError("robot.yaml not found; pass config or set RP_ROBOT_CONFIG")


def load_motors(path: Path) -> tuple[list[dict], int]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    motors = data.get("motors") if isinstance(data, dict) else None
    if not isinstance(motors, dict):
        raise ValueError("robot.yaml has no motors mapping")
    interfaces = motors.get("motor_interface")
    counts = motors.get("motor_num")
    interface_types = motors.get("motor_interface_type")
    types = motors.get("motor_type")
    ids = motors.get("motor_id")
    models = motors.get("motor_model")
    zeros = motors.get("motor_zero_offset", [])
    if not all(isinstance(value, list) for value in
               (interfaces, counts, interface_types, types, ids, models, zeros)):
        raise ValueError("robot.yaml motor arrays are incomplete")
    if not len(interfaces) == len(counts) == len(interface_types) == len(types):
        raise ValueError("robot.yaml motor bus arrays have different lengths")
    if len(ids) != sum(counts) or len(models) != len(ids) or len(zeros) != len(ids):
        raise ValueError("robot.yaml motor IDs, models or zero offsets do not match bus counts")
    try:
        master = int(motors.get("master_id_offset", 0) or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid master_id_offset") from exc

    entries = []
    index = 0
    for interface, count, interface_type, motor_type in zip(
            interfaces, counts, interface_types, types):
        if type(count) is not int or count < 0:
            raise ValueError("invalid motor_num")
        for _ in range(count):
            entries.append({
                "id": ids[index],
                "interface": interface,
                "interfaceType": interface_type,
                "type": motor_type,
                "model": models[index],
                "zeroOffset": float(zeros[index]),
            })
            index += 1
    return entries, master


def _motors_py():
    try:
        import motors_py
        return motors_py
    except ImportError:
        site = (Path("/opt/roboparty/lib")
                / f"python{sys.version_info.major}.{sys.version_info.minor}" / "site-packages")
        if site.is_dir():
            sys.path.insert(0, str(site))
        import motors_py
        return motors_py


def listen_feedback(interfaces: list[str], seconds: float) -> dict[tuple[str, int], int]:
    """Count feedback frames per (interface, can_id) without sending anything."""
    sockets = []
    for interface in sorted(set(interfaces)):
        try:
            bus = socket.socket(socket.PF_CAN, socket.SOCK_RAW, socket.CAN_RAW)
            bus.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FD_FRAMES, 1)
            bus.bind((interface,))
            bus.setblocking(False)
            sockets.append((interface, bus))
        except OSError:
            continue
    counts: dict[tuple[str, int], int] = {}
    deadline = time.monotonic() + max(0.0, seconds)
    try:
        while time.monotonic() < deadline:
            for interface, bus in sockets:
                try:
                    frame = bus.recv(72)
                except (BlockingIOError, InterruptedError):
                    continue
                except OSError:
                    continue
                if len(frame) < 72:
                    continue
                can_id, length = struct.unpack("=IB", frame[:5])
                if length not in (8, 12):
                    continue
                key = (interface, can_id & CAN_EFF_MASK)
                counts[key] = counts.get(key, 0) + 1
            time.sleep(0.005)
    finally:
        for _, bus in sockets:
            bus.close()
    return counts


def read(config: Optional[str] = None, settle: float = SETTLE_SECONDS,
         driver_class=None, feedback_counter: Optional[Callable] = None,
         now: Optional[Callable[[], str]] = None) -> dict:
    path = config_path(config)
    motors, master = load_motors(path)
    if driver_class is None:
        driver_class = _motors_py().MotorDriver
    if feedback_counter is None:
        feedback_counter = listen_feedback
    drivers = []
    warnings = []
    for motor in motors:
        try:
            driver = driver_class.create_motor(
                motor["id"], motor["interfaceType"], motor["interface"],
                motor["type"], motor["model"], master, motor["zeroOffset"])
            drivers.append((motor, driver))
        except Exception as exc:  # missing library / unknown model / CAN down
            warnings.append(f"motor {motor['id']}: create failed: {exc}")
    counts = feedback_counter([m["interface"] for m in motors], settle)
    results = []
    for motor, driver in drivers:
        feedback = counts.get((motor["interface"], motor["id"]), 0) > 0
        entry = dict(motor, feedback=feedback, error=None, errorName=None,
                     position=None, speed=None, current=None, temperature=None)
        if feedback:
            try:
                code = int(driver.get_error_id() or 0)
                entry.update(
                    error=code, errorName=error_name(motor["type"], code),
                    position=float(driver.get_motor_pos()),
                    speed=float(driver.get_motor_spd()),
                    current=float(driver.get_motor_current()),
                    temperature=float(driver.get_motor_temperature()),
                )
            except Exception as exc:
                warnings.append(f"motor {motor['id']}: read failed: {exc}")
        else:
            warnings.append(f"motor {motor['id']}: no feedback on {motor['interface']}")
        results.append(entry)
    stamp = (now or (lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()))()
    return {
        "schemaVersion": 1,
        "server": os.environ.get("RP_TUI_SERVER") or "robopi-tui",
        "config": str(path),
        "collectedAt": stamp,
        "settleSeconds": settle,
        "motors": results,
        "warnings": warnings,
    }
